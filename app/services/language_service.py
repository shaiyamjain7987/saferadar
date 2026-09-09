import os
import re

import requests
from flask import current_app, has_app_context

# Lightweight script detection used before calling translation.
LANGUAGE_SCRIPTS = (
    ("hi", re.compile(r"[\u0900-\u097F]")),
    ("bn", re.compile(r"[\u0980-\u09FF]")),
    ("gu", re.compile(r"[\u0A80-\u0AFF]")),
    ("pa", re.compile(r"[\u0A00-\u0A7F]")),
    ("ta", re.compile(r"[\u0B80-\u0BFF]")),
    ("te", re.compile(r"[\u0C00-\u0C7F]")),
    ("kn", re.compile(r"[\u0C80-\u0CFF]")),
    ("ml", re.compile(r"[\u0D00-\u0D7F]")),
    ("or", re.compile(r"[\u0B00-\u0B7F]")),
    ("ur", re.compile(r"[\u0600-\u06FF]")),
)

# Common safety phrases (Hindi -> English) for offline demo
PHRASE_MAP = {
    "मशीन का पावर बंद नहीं था": "Machine power was not switched off",
    "लॉकआउट नहीं किया": "Lockout was not done",
    "गैस टेस्ट नहीं किया": "Gas test was not performed",
    "परमिट नहीं था": "Permit was missing",
    "ऊंचाई पर काम": "Working at height",
    "हार्नेस नहीं पहना": "Harness was not worn",
    "पाइपलाइन में आग लग गई": "Fire broke out near pipeline",
    "पाइपलाइन के पास आग लग गई": "Fire broke out near pipeline",
    "पाइपलाइन में आग लगी": "Fire broke out near pipeline",
    "आग लग गई": "Fire broke out",
}


def detect_language(text):
    if not text:
        return "en"
    for language, script in LANGUAGE_SCRIPTS:
        if script.search(text):
            return language
    return "en"


def _bhashini_translate(text, source_lang):
    """Optional Bhashini translation if API key is configured."""
    api_key = None
    if has_app_context():
        api_key = current_app.config.get("BHASHINI_API_KEY")
    api_key = api_key or os.environ.get("BHASHINI_API_KEY")
    if not api_key or source_lang == "en":
        return None

    # Placeholder endpoint shape — replace with your Bhashini pipeline URL when issued.
    endpoint = os.environ.get(
        "BHASHINI_TRANSLATE_URL",
        "https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
    )
    service_id = os.environ.get("BHASHINI_TRANSLATE_SERVICE_ID")
    try:
        translation_config = {
            "language": {
                "sourceLanguage": source_lang,
                "targetLanguage": "en",
            }
        }
        if service_id:
            translation_config["serviceId"] = service_id

        resp = requests.post(
            endpoint,
            headers={"Authorization": api_key, "Content-Type": "application/json"},
            json={
                "pipelineTasks": [
                    {
                        "taskType": "translation",
                        "config": translation_config,
                    }
                ],
                "inputData": {"input": [{"source": text}]},
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        return _translation_from_response(data)
    except Exception as exc:
        if has_app_context():
            current_app.logger.warning("Bhashini translate failed: %s", exc)
        return None


def _translation_from_response(value):
    """Extract translated text from the supported Bhashini response shapes."""
    if isinstance(value, dict):
        for key in ("target", "tgt", "translatedText", "translation", "text"):
            result = value.get(key)
            if isinstance(result, str) and result.strip():
                return result.strip()
        for child in value.values():
            result = _translation_from_response(child)
            if result:
                return result
    elif isinstance(value, list):
        for child in value:
            result = _translation_from_response(child)
            if result:
                return result
    return None


def translate_to_english(text, source_lang):
    if not text:
        return text
    if source_lang in (None, "", "en"):
        return text

    # 1) Offline phrase map
    for hi, en in PHRASE_MAP.items():
        if hi in text:
            return text.replace(hi, en)

    # 2) Bhashini if configured
    translated = _bhashini_translate(text, source_lang)
    if translated:
        return translated

    # 3) Keep original — keyword NLP still works on mixed English terms
    return text
