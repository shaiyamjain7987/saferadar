import os

from openai import OpenAI
from flask import current_app


def _openai_client(api_key):
    return OpenAI(api_key=api_key)


def transcribe_audio(file_path):
    """Transcribe with OpenAI Whisper; fall back to SpeechRecognition, then demo text."""
    api_key = current_app.config.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")

    if api_key:
        try:
            client = _openai_client(api_key)
            with open(file_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                )
            text = (transcription.text or "").strip()
            if text:
                return text
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
            return text.strip()
    except Exception as e:
        current_app.logger.warning("SpeechRecognition fallback failed: %s", e)

    current_app.logger.warning("Using demo transcript fallback for %s", file_path)
    return "Machine power was not switched off during maintenance."
