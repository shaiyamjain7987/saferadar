import os
import uuid
from datetime import datetime

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from . import worker_bp
from ..constants import AREAS
from ..extensions import db
from ..models import Alert, Report
from ..services.language_service import detect_language, translate_to_english
from ..services.nlp_service import analyze_safety_text
from ..services.risk_service import calculate_sif_score


def _save_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    upload_dir = os.path.join(current_app.root_path, "static", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    ext = os.path.splitext(secure_filename(file_storage.filename))[1].lower() or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    file_storage.save(os.path.join(upload_dir, filename))
    return filename


def _build_report_from_form():
    description = (request.form.get("description") or "").strip()
    location = (request.form.get("location") or "").strip()
    area = (request.form.get("area") or "").strip()
    date_raw = (request.form.get("report_date") or "").strip()

    if not (description and location and area and date_raw):
        return None, "All required fields must be filled."

    try:
        report_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
    except ValueError:
        return None, "Invalid date format."

    lang = detect_language(description)
    english_text = translate_to_english(description, lang)
    analysis = analyze_safety_text(english_text)
    risk = calculate_sif_score(analysis)
    image_filename = _save_image(request.files.get("image"))

    report = Report(
        worker_id=current_user.id,
        site_id=current_user.site_id,
        report_date=report_date,
        location=location,
        area=area,
        description=english_text,
        original_language=lang,
        image_filename=image_filename,
        activity=analysis.get("activity"),
        hazard=analysis.get("hazard"),
        precursor=analysis.get("precursor"),
        barrier_failure=analysis.get("barrier_failure"),
        life_saving_rule=analysis.get("life_saving_rule"),
        sif_potential=bool(analysis.get("sif_potential") or risk.get("risk_level") == "HIGH"),
        sif_score=risk.get("score"),
        risk_level=risk.get("risk_level"),
        explanation=risk.get("explanation"),
        status="Open",
    )
    return report, None


@worker_bp.route("/")
@worker_bp.route("/dashboard")
@login_required
def dashboard():
    if not current_user.is_worker:
        return redirect(url_for("sitehead.dashboard"))

    reports = (
        Report.query.filter_by(worker_id=current_user.id)
        .order_by(Report.report_date.desc(), Report.id.desc())
        .all()
    )
    sif_count = sum(1 for r in reports if r.sif_potential)
    return render_template(
        "worker/dashboard.html",
        reports=reports,
        total_count=len(reports),
        sif_count=sif_count,
    )


@worker_bp.route("/report/new", methods=["GET", "POST"])
@login_required
def report_new():
    if not current_user.is_worker:
        return redirect(url_for("sitehead.dashboard"))

    if request.method == "POST":
        report, error = _build_report_from_form()
        if error:
            flash(error, "danger")
            return render_template("worker/report_form.html", areas=AREAS)

        db.session.add(report)
        db.session.flush()

        if report.risk_level == "HIGH" or report.sif_potential:
            db.session.add(
                Alert(
                    site_id=report.site_id,
                    title="HIGH SIF ALERT",
                    message=(
                        f"High risk report #{report.id}: {report.precursor or 'SIF precursor'}. "
                        f"{report.explanation or ''}"
                    ).strip(),
                    level="CRITICAL",
                )
            )

        db.session.commit()
        flash("Report submitted successfully.", "success")
        return redirect(url_for("worker.report_detail", report_id=report.id))

    return render_template("worker/report_form.html", areas=AREAS)


@worker_bp.route("/report/<int:report_id>")
@login_required
def report_detail(report_id):
    if not current_user.is_worker:
        return redirect(url_for("sitehead.dashboard"))

    report = Report.query.filter_by(id=report_id, worker_id=current_user.id).first_or_404()
    return render_template("worker/report_detail.html", report=report)
