import os
import re

import requests
from flask import current_app, has_app_context

# Lightweight language heuristics for demo (no external API required).
DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
ASSAMESE_BENGALI_RE = re.compile(r"[\u0980-\u09FF]")

# Common safety phrases (Hindi -> English) for offline demo
PHRASE_MAP = {
    "मशीन का पावर बंद नहीं था": "Machine power was not switched off",
    "लॉकआउट नहीं किया": "Lockout was not done",
    "गैस टेस्ट नहीं किया": "Gas test was not performed",
    "परमिट नहीं था": "Permit was missing",
    "ऊंचाई पर काम": "Working at height",
    "हार्नेस नहीं पहना": "Harness was not worn",
}


def detect_language(text):
    if not text:
        return "en"
    if DEVANAGARI_RE.search(text):
        return "hi"
    if ASSAMESE_BENGALI_RE.search(text):
        return "as"
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
    try:
        resp = requests.post(
            endpoint,
            headers={"Authorization": api_key, "Content-Type": "application/json"},
            json={
                "pipelineTasks": [
                    {
                        "taskType": "translation",
                        "config": {
                            "language": {
                                "sourceLanguage": source_lang,
                                "targetLanguage": "en",
                            }
                        },
                    }
                ],
                "inputData": {"input": [{"source": text}]},
            },
            timeout=20,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        # Best-effort parse across common Bhashini response shapes
        for key in ("pipelineResponse", "output", "data"):
            block = data.get(key)
            if isinstance(block, list) and block:
                first = block[0]
                if isinstance(first, dict):
                    for out_key in ("output", "target", "tgt"):
                        val = first.get(out_key)
                        if isinstance(val, list) and val:
                            item = val[0]
                            if isinstance(item, dict) and item.get("target"):
                                return item["target"]
                            if isinstance(item, str):
                                return item
                        if isinstance(val, str):
                            return val
        return None
    except Exception as exc:
        if has_app_context():
            current_app.logger.warning("Bhashini translate failed: %s", exc)
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
