import os
import re

import requests
from flask import current_app, has_app_context
from openai import OpenAI

# Lightweight script detection used before calling translation.
LANGUAGE_SCRIPTS = (
    ("as", re.compile(r"[\u0980-\u09FF]")),
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

SUPPORTED_LANGUAGE_CODES = {
    "en", "hi", "bn", "as", "gu", "pa", "mr", "ta", "te", "kn", "ml", "or", "ur"
}

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
    "पाइपलाइन में आग लग गयी है": "Fire broke out near pipeline",
    "पाइपलाइन के पास आग लग गयी है": "Fire broke out near pipeline",
    "आग लग गई": "Fire broke out",
    "आग लग गई है": "Fire broke out",
    "आग लग गयी": "Fire broke out",
    "आग लग गयी है": "Fire broke out",
    "आग लगी है": "Fire broke out",
    "आग लगी": "Fire broke out",
    "মেশিনের পাওয়ার বন্ধ ছিল না": "Machine power was not switched off",
    "লকআউট করা হয়নি": "Lockout was not done",
    "গ্যাস পরীক্ষা করা হয়নি": "Gas test was not performed",
    "পারমিট ছিল না": "Permit was missing",
    "উচ্চতায় কাজ": "Working at height",
    "হারনেস পরা হয়নি": "Harness was not worn",
    "இயந்திரத்தின் மின்சாரம் நிறுத்தப்படவில்லை": "Machine power was not switched off",
    "லாக்அவுட் செய்யப்படவில்லை": "Lockout was not done",
    "எரிவாயு சோதனை செய்யப்படவில்லை": "Gas test was not performed",
    "அனுமதி இல்லை": "Permit was missing",
    "உயரத்தில் வேலை": "Working at height",
    "சேணம் அணியவில்லை": "Harness was not worn",
    "యంత్రం పవర్ ఆఫ్ చేయలేదు": "Machine power was not switched off",
    "లాక్‌అవుట్ చేయలేదు": "Lockout was not done",
    "గ్యాస్ పరీక్ష చేయలేదు": "Gas test was not performed",
    "పర్మిట్ లేదు": "Permit was missing",
    "ఎత్తులో పని": "Working at height",
    "హార్నెస్ ధరించలేదు": "Harness was not worn",
    "ಮೆಷಿನ್ ಪವರ್ ಆಫ್ ಮಾಡಿರಲಿಲ್ಲ": "Machine power was not switched off",
    "ಲಾಕೌಟ್ ಮಾಡಿರಲಿಲ್ಲ": "Lockout was not done",
    "ಗ್ಯಾಸ್ ಟೆಸ್ಟ್ ಮಾಡಿರಲಿಲ್ಲ": "Gas test was not performed",
    "ಪರ್ಮಿಟ್ ಇರಲಿಲ್ಲ": "Permit was missing",
    "ಎತ್ತರದಲ್ಲಿ ಕೆಲಸ": "Working at height",
    "হার্নেস পরা হয়নি": "Harness was not worn",
}


def detect_language(text, language_hint=None):
    hint = (language_hint or "").strip().lower().replace("_", "-")
    if hint and hint != "auto":
        hint = hint.split("-")[0]
        if hint in SUPPORTED_LANGUAGE_CODES:
            return hint
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
        inference_key = (
            current_app.config.get("BHASHINI_INFERENCE_KEY")
            if has_app_context()
            else None
        ) or api_key
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
            headers={
                "Authorization": inference_key,
                "userID": os.environ.get("BHASHINI_USER_ID", ""),
                "ulcaApiKey": api_key,
                "Content-Type": "application/json",
            },
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


def _openai_translate(text, source_lang):
    api_key = None
    if has_app_context():
        api_key = current_app.config.get("OPENAI_API_KEY")
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key or source_lang == "en":
        return None

    try:
        response = OpenAI(api_key=api_key).chat.completions.create(
            model=os.environ.get("OPENAI_TRANSLATION_MODEL", "gpt-4o-mini"),
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "Translate the user's safety report to concise English. Return only the translation.",
                },
                {"role": "user", "content": text},
            ],
        )
        translated = response.choices[0].message.content
        return translated.strip() if translated else None
    except Exception as exc:
        if has_app_context():
            current_app.logger.warning("OpenAI translation failed: %s", exc)
        return None


def translate_to_english(text, source_lang):
    if not text:
        return text
    if source_lang in (None, "", "en"):
        return text

    # 1) Offline phrase map. Replace matching phrases while preserving any
    # surrounding location or activity details in the report.
    translated_text = text
    matched_phrase = False
    for phrase, english in sorted(PHRASE_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if phrase in translated_text:
            translated_text = translated_text.replace(phrase, english)
            matched_phrase = True
    if matched_phrase:
        return translated_text

    # 2) Bhashini if configured
    translated = _bhashini_translate(text, source_lang)
    if translated:
        return translated

    # 3) OpenAI fallback when Bhashini is unavailable.
    translated = _openai_translate(text, source_lang)
    if translated:
        return translated

    # 4) Keep original rather than dropping the worker's report.
    return text
