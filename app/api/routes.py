import os
from datetime import date, datetime

from flask import current_app, jsonify, request
from flask_login import current_user, login_required

from . import api_bp
from ..extensions import db
from ..models import Alert, CorrectiveAction, Report, User
from ..services.exotel_service import status_summary as exotel_status
from ..services.report_pipeline import (
    build_payload_from_audio,
    build_payload_from_text,
    create_report_from_analysis,
)


def _analyze_audio_file(audio_file):
    upload_dir = current_app.config.get("UPLOAD_FOLDER", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    filename = audio_file.filename or "recording.webm"
    safe_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
    file_path = os.path.join(upload_dir, safe_name)
    audio_file.save(file_path)
    payload = build_payload_from_audio(file_path, filename=safe_name)
    payload["file_path"] = file_path
    return payload


@api_bp.route("/health", methods=["GET"])
def health():
    """All API integration status (no secret values)."""
    openai_key = bool(current_app.config.get("OPENAI_API_KEY"))
    bhashini = bool(current_app.config.get("BHASHINI_API_KEY"))
    exotel = exotel_status()
    database = {"ok": True}
    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception as exc:
        db.session.rollback()
        database = {"ok": False, "error": type(exc).__name__}
    return jsonify(
        {
            "ok": True,
            "database": database,
            "openai": {
                "configured": openai_key,
                "note": "Needs billing credits for live Whisper/embeddings; falls back otherwise",
            },
            "bhashini": {
                "configured": bhashini,
                "note": "Optional — offline Hindi phrase map used if missing",
            },
            "exotel": exotel,
            "pending": []
            if exotel.get("ready_for_webhooks")
            else ["PUBLIC_BASE_URL (ngrok HTTPS URL)"],
        }
    )


@api_bp.route("/auth/me", methods=["GET"])
@login_required
def get_me():
    return jsonify(
        {
            "id": current_user.id,
            "name": current_user.name,
            "role": current_user.role,
            "site_id": current_user.site_id,
        }
    )


@api_bp.route("/reports/voice", methods=["POST"])
@login_required
def upload_voice_report():
    if "audio" not in request.files:
        return jsonify({"success": False, "error": "No audio file provided"}), 400

    payload = _analyze_audio_file(request.files["audio"])
    return jsonify(
        {
            "success": True,
            "transcript": payload["transcript"],
            "language": payload["language"],
            "translated_text": payload["translated_text"],
            "analysis": payload["analysis"],
            "risk": payload["risk"],
        }
    )


@api_bp.route("/demo/voice", methods=["POST"])
def demo_voice_report():
    """Public jury/demo endpoint used by /ivr/demo — no login required."""
    if "audio" not in request.files:
        json_body = request.get_json(silent=True) or {}
        text = (request.form.get("text") or json_body.get("text") or "").strip()
        if not text:
            return jsonify({"success": False, "error": "No audio or text provided"}), 400
        payload = build_payload_from_text(text, filename="demo_text.txt")
        worker = User.query.filter_by(email="worker1@oil.com").first()
        report = create_report_from_analysis(worker, payload, save_audio=False) if worker else None
        return jsonify(
            {
                "success": True,
                "transcript": payload["transcript"],
                "language": payload["language"],
                "translated_text": payload["translated_text"],
                "analysis": payload["analysis"],
                "risk": payload["risk"],
                "report_id": report.id if report else None,
            }
        )

    payload = _analyze_audio_file(request.files["audio"])
    worker = User.query.filter_by(email="worker1@oil.com").first()
    report = create_report_from_analysis(worker, payload, save_audio=True) if worker else None
    return jsonify(
        {
            "success": True,
            "transcript": payload["transcript"],
            "language": payload["language"],
            "translated_text": payload["translated_text"],
            "analysis": payload["analysis"],
            "risk": payload["risk"],
            "report_id": report.id if report else None,
        }
    )


@api_bp.route("/reports", methods=["POST"])
@login_required
def submit_report():
    data = request.json or {}
    date_raw = data.get("report_date")
    report_date = date.today()
    if date_raw:
        try:
            report_date = datetime.strptime(str(date_raw)[:10], "%Y-%m-%d").date()
        except ValueError:
            pass

    analysis = data.get("analysis") or {}
    risk = data.get("risk") or {}
    translated_description = data.get("description") or ""
    detected_language = data.get("language") or "en"
    if not analysis and data.get("description"):
        payload = build_payload_from_text(data["description"])
        analysis = payload["analysis"]
        risk = payload["risk"]
        translated_description = payload["translated_text"]
        detected_language = payload["language"]

    report = Report(
        worker_id=current_user.id,
        site_id=current_user.site_id,
        report_date=report_date,
        location=data.get("location") or "Unspecified",
        area=data.get("area") or "Other",
        description=translated_description,
        original_language=detected_language,
        activity=analysis.get("activity"),
        hazard=analysis.get("hazard"),
        precursor=analysis.get("precursor"),
        barrier_failure=analysis.get("barrier_failure"),
        life_saving_rule=analysis.get("life_saving_rule"),
        sif_potential=(risk.get("risk_level") == "HIGH") or bool(analysis.get("sif_potential")),
        sif_score=risk.get("score"),
        risk_level=risk.get("risk_level"),
        explanation=risk.get("explanation"),
    )

    db.session.add(report)
    db.session.flush()

    if report.risk_level == "HIGH" or report.sif_potential:
        db.session.add(
            Alert(
                site_id=report.site_id,
                title="HIGH SIF ALERT",
                message=f"High risk report submitted: {report.precursor}. {report.explanation}",
                level="CRITICAL",
            )
        )
    db.session.commit()
    return jsonify({"success": True, "report_id": report.id})


@api_bp.route("/reports", methods=["GET"])
@login_required
def get_reports():
    query = Report.query
    if current_user.is_worker:
        query = query.filter_by(worker_id=current_user.id)
    else:
        query = query.filter_by(site_id=current_user.site_id)

    reports = query.order_by(Report.created_at.desc()).all()
    return jsonify(
        {
            "reports": [
                {
                    "id": r.id,
                    "date": r.report_date.isoformat() if r.report_date else None,
                    "location": r.location,
                    "description": r.description,
                    "risk_level": r.risk_level,
                    "precursor": r.precursor,
                    "status": r.status,
                }
                for r in reports
            ]
        }
    )


@api_bp.route("/dashboard/summary", methods=["GET"])
@login_required
def dashboard_summary():
    reports = Report.query.filter_by(site_id=current_user.site_id).all()
    total = len(reports)
    high_sif = sum(1 for r in reports if r.risk_level == "HIGH")
    med_risk = sum(1 for r in reports if r.risk_level == "MEDIUM")
    low_risk = sum(1 for r in reports if r.risk_level == "LOW")
    open_actions = (
        CorrectiveAction.query.join(Report)
        .filter(Report.site_id == current_user.site_id, CorrectiveAction.status == "Open")
        .count()
    )
    precursors = {}
    for r in reports:
        if r.precursor:
            precursors[r.precursor] = precursors.get(r.precursor, 0) + 1
    recurring = sum(1 for c in precursors.values() if c > 1)

    return jsonify(
        {
            "total_reports": total,
            "high_sif_reports": high_sif,
            "medium_risk": med_risk,
            "low_risk": low_risk,
            "open_actions": open_actions,
            "recurring_precursors": recurring,
        }
    )
