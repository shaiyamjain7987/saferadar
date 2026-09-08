"""Shared analyze → score → save report pipeline used by web, API, and IVR."""

from datetime import date

from ..extensions import db
from ..models import Alert, AudioRecord, Report


def build_payload_from_text(text, language="en", translated_text=None, filename="text_report.txt"):
    from .language_service import detect_language, translate_to_english
    from .nlp_service import analyze_safety_text
    from .risk_service import calculate_sif_score

    lang = language or detect_language(text)
    english = translated_text if translated_text is not None else translate_to_english(text, lang)
    analysis = analyze_safety_text(english)
    risk = calculate_sif_score(analysis)
    return {
        "filename": filename,
        "transcript": text,
        "language": lang,
        "translated_text": english,
        "analysis": analysis,
        "risk": risk,
    }


def build_payload_from_audio(file_path, filename=None):
    from .language_service import detect_language, translate_to_english
    from .nlp_service import analyze_safety_text
    from .risk_service import calculate_sif_score
    from .speech_service import transcribe_audio

    transcript = transcribe_audio(file_path)
    lang = detect_language(transcript)
    english = translate_to_english(transcript, lang)
    analysis = analyze_safety_text(english)
    risk = calculate_sif_score(analysis)
    return {
        "filename": filename or file_path,
        "transcript": transcript,
        "language": lang,
        "translated_text": english,
        "analysis": analysis,
        "risk": risk,
    }


def create_report_from_analysis(worker, payload, save_audio=True):
    analysis = payload["analysis"]
    risk = payload["risk"]

    audio_id = None
    if save_audio and payload.get("filename"):
        audio = AudioRecord(
            filename=payload["filename"],
            transcript=payload.get("transcript"),
            translated_text=payload.get("translated_text"),
            language_detected=payload.get("language"),
        )
        db.session.add(audio)
        db.session.flush()
        audio_id = audio.id

    report = Report(
        worker_id=worker.id,
        site_id=worker.site_id,
        report_date=date.today(),
        location=payload.get("location") or "IVR / Voice Report",
        area=payload.get("area") or "Maintenance Area",
        description=payload.get("translated_text") or payload.get("transcript") or "",
        original_language=payload.get("language") or "en",
        audio_record_id=audio_id,
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
    return report
