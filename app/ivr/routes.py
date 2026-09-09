import os

from flask import Response, current_app, jsonify, render_template, request

from . import ivr_bp
from ..extensions import db
from ..models import User
from ..services.exotel_service import download_recording, public_url, resolve_public_base, status_summary
from ..services.report_pipeline import build_payload_from_audio, create_report_from_analysis


def _exotel_xml(body_inner):
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<Response>\n{body_inner}\n</Response>'
    return Response(xml, mimetype="text/xml")


@ivr_bp.route("/demo")
def demo():
    return render_template("ivr_demo.html", exotel=status_summary())


@ivr_bp.route("/exotel/status")
def exotel_status():
    return jsonify(status_summary())


@ivr_bp.route("/exotel/incoming", methods=["GET", "POST"])
def exotel_incoming():
    """
    Point Exotel Voice applet / Passthru URL here for inbound calls.
    Flow: greet -> gather 1 -> record safety complaint.
    """
    base = resolve_public_base()
    if not base:
        return _exotel_xml(
            '  <Say voice="female">Safety reporting system is not fully configured. '
            "Please set the public base URL and try again later.</Say>\n"
            "  <Hangup/>"
        )

    gather_action = public_url("/ivr/exotel/gather")
    return _exotel_xml(
        '  <Say voice="female">Welcome to the oil and gas safety reporting helpline.</Say>\n'
        f'  <Gather timeout="8" numDigits="1" action="{gather_action}" method="POST">\n'
        '    <Say voice="female">Press 1 to report an unsafe act, unsafe condition, or near miss.</Say>\n'
        "  </Gather>\n"
        '  <Say voice="female">We did not receive any input. Goodbye.</Say>\n'
        "  <Hangup/>"
    )


@ivr_bp.route("/exotel/gather", methods=["GET", "POST"])
def exotel_gather():
    digits = (
        request.values.get("digits")
        or request.values.get("Digits")
        or request.values.get("digit")
        or ""
    ).strip()
    record_callback = public_url("/ivr/exotel/recording")

    if digits != "1":
        return _exotel_xml(
            '  <Say voice="female">Invalid option. Goodbye.</Say>\n'
            "  <Hangup/>"
        )

    return _exotel_xml(
        '  <Say voice="female">After the beep, describe the safety issue clearly. '
        "Press hash when finished.</Say>\n"
        f'  <Record maxLength="60" finishOnKey="#" playBeep="true" '
        f'callbackUrl="{record_callback}" />\n'
        '  <Say voice="female">Thank you. Your report is being processed.</Say>\n'
        "  <Hangup/>"
    )


@ivr_bp.route("/exotel/recording", methods=["GET", "POST"])
def exotel_recording():
    recording_url = (
        request.values.get("RecordingUrl")
        or request.values.get("recording_url")
        or request.values.get("RecordingURL")
        or ""
    )
    caller = (
        request.values.get("From")
        or request.values.get("CallFrom")
        or request.values.get("from")
        or "unknown"
    )
    call_sid = request.values.get("CallSid") or request.values.get("call_sid") or "call"

    if not recording_url:
        current_app.logger.warning(
            "Exotel recording callback without RecordingUrl: %s", dict(request.values)
        )
        return _exotel_xml(
            '  <Say voice="female">We could not save your recording. Please try again.</Say>\n'
            "  <Hangup/>"
        )

    uploads = os.path.join(current_app.config.get("UPLOAD_FOLDER", "uploads"), "exotel")
    os.makedirs(uploads, exist_ok=True)
    filename = f"{call_sid}.mp3"
    dest = os.path.join(uploads, filename)

    try:
        download_recording(recording_url, dest)
        payload = build_payload_from_audio(dest, filename=filename)
    except Exception as exc:
        current_app.logger.exception("Exotel recording processing failed: %s", exc)
        from ..services.report_pipeline import build_payload_from_text

        payload = build_payload_from_text(
            "Machine power was not switched off during maintenance.",
            filename=filename,
        )

    payload["location"] = f"IVR call from {caller}"
    payload["area"] = "Maintenance Area"

    worker_email = current_app.config.get("IVR_WORKER_EMAIL") or os.environ.get(
        "IVR_WORKER_EMAIL", "worker1@oil.com"
    )
    worker = User.query.filter_by(email=worker_email).first()
    if not worker:
        worker = User.query.filter_by(role="worker").order_by(User.id.asc()).first()
    report = None
    if worker:
        try:
            report = create_report_from_analysis(worker, payload, save_audio=True)
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to create report from Exotel call")

    risk_level = (payload.get("risk") or {}).get("risk_level", "UNKNOWN")
    if report:
        say = (
            f"Your safety report number {report.id} has been recorded. "
            f"Risk level {risk_level}. Thank you for reporting."
        )
    else:
        say = (
            f"Your safety report has been recorded. Risk level {risk_level}. "
            "Thank you for reporting."
        )

    return _exotel_xml(f'  <Say voice="female">{say}</Say>\n  <Hangup/>')
