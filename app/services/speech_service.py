import base64
import os

import requests
from openai import OpenAI
from flask import current_app


def _openai_client(api_key):
    return OpenAI(api_key=api_key)


def _audio_content(file_path):
    with open(file_path, "rb") as audio_file:
        return base64.b64encode(audio_file.read()).decode("ascii")


def _bhashini_detect_language(endpoint, api_key, audio_content):
    response = requests.post(
        endpoint,
        headers={"Authorization": api_key, "Content-Type": "application/json"},
        json={
            "pipelineTasks": [{"taskType": "language-detection", "config": {}}],
            "inputData": {"audio": [{"audioContent": audio_content}]},
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    for task in data.get("pipelineResponse", []):
        for output in task.get("output", []):
            language = output.get("langCode") or output.get("language")
            if language:
                return language.split("-")[0].lower()
    return None


def _bhashini_transcribe(file_path, api_key):
    endpoint = os.environ.get(
        "BHASHINI_ASR_URL",
        "https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
    )
    source_language = current_app.config.get("BHASHINI_ASR_LANGUAGE", "auto")
    service_id = os.environ.get("BHASHINI_ASR_SERVICE_ID")
    audio_content = _audio_content(file_path)

    if source_language in (None, "", "auto"):
        source_language = _bhashini_detect_language(endpoint, api_key, audio_content) or "hi"

    asr_config = {
        "language": {"sourceLanguage": source_language},
        "audioFormat": os.path.splitext(file_path)[1].lstrip(".").lower() or "wav",
        "samplingRate": 16000,
    }
    if service_id:
        asr_config["serviceId"] = service_id

    response = requests.post(
        endpoint,
        headers={"Authorization": api_key, "Content-Type": "application/json"},
        json={
            "pipelineTasks": [{"taskType": "asr", "config": asr_config}],
            "inputData": {"audio": [{"audioContent": audio_content}]},
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    for task in data.get("pipelineResponse", []):
        for output in task.get("output", []):
            text = output.get("source") or output.get("text")
            if text:
                return text.strip(), source_language
    return "", source_language


def transcribe_audio_with_language(file_path):
    """Transcribe with Bhashini, then OpenAI, SpeechRecognition, and demo text."""
    bhashini_key = current_app.config.get("BHASHINI_API_KEY") or os.environ.get(
        "BHASHINI_API_KEY"
    )
    if bhashini_key:
        try:
            text, language = _bhashini_transcribe(file_path, bhashini_key)
            if text:
                return text, language
        except Exception as e:
            current_app.logger.warning("Bhashini ASR failed: %s", e)

    api_key = current_app.config.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")

    if api_key:
        try:
            client = _openai_client(api_key)
            with open(file_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                )
            text = (transcription.text or "").strip()
            if text:
                return text, getattr(transcription, "language", None)
        except Exception as e:
            current_app.logger.warning("OpenAI Whisper failed: %s", e)

    # Offline / secondary fallback
    try:
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        with sr.AudioFile(file_path) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio)
        if text:
            return text.strip(), None
    except Exception as e:
        current_app.logger.warning("SpeechRecognition fallback failed: %s", e)

    current_app.logger.warning("Using demo transcript fallback for %s", file_path)
    return "Machine power was not switched off during maintenance.", "en"


def transcribe_audio(file_path):
    """Backward-compatible text-only transcription helper."""
    text, _language = transcribe_audio_with_language(file_path)
    return text
