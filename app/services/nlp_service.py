import os
import re
import numpy as np
from openai import OpenAI
from flask import current_app

# IOGP Life-Saving Rules and Keyword Mappings
IOGP_RULES = {
    "Energy Isolation": ["power", "switch", "isolate", "loto", "lockout", "energy", "electrical", "valve", "machine power was not switched off"],
    "Working at Height": ["fall", "height", "harness", "scaffold", "edge", "drop", "roof"],
    "Confined Space": ["confined", "tank", "gas", "oxygen", "vessel", "ventilation", "atmosphere"],
    "Line of Fire": ["struck", "moving", "dropped", "crush", "suspended", "load", "swinging"],
    "Hot Work": ["welding", "spark", "fire", "flammable", "combustible", "hot work"],
    "Driving": ["vehicle", "speed", "seatbelt", "crash", "road", "driving", "brake"],
    "Safe Mechanical Lifting": ["crane", "lift", "hoist", "rigging", "sling"],
    "Bypassing Safety Controls": ["bypass", "interlock", "disable", "override", "guard"],
    "Work Authorization": ["permit", "unauthorized", "clearance", "authorization"]
}

SIF_KEYWORDS = ["fatal", "serious", "crush", "fall", "explosion", "fire", "electrocution", "toxic", "amputation", "suspended", "power", "height", "switch"]

# Precompute descriptions for categories
rule_descriptions = {
    "Energy Isolation": "Failure to properly isolate and lockout electrical or mechanical energy before maintenance.",
    "Working at Height": "Failure to use fall protection when working at heights above standard levels.",
    "Confined Space": "Entering a confined space without proper testing or authorization.",
    "Line of Fire": "Positioning oneself in the path of a moving object, suspended load, or released energy.",
    "Hot Work": "Performing spark-producing work without clearing combustibles or obtaining a permit.",
    "Driving": "Unsafe driving practices including speeding or not wearing a seatbelt.",
    "Safe Mechanical Lifting": "Improper rigging or lifting operations involving cranes or hoists.",
    "Bypassing Safety Controls": "Disabling or overriding critical safety guards, interlocks, or alarms.",
    "Work Authorization": "Proceeding with high-risk work without valid authorization or permits."
}

_rule_embs = None

def get_openai_embedding(text, client):
    response = client.embeddings.create(input=text, model="text-embedding-3-small")
    return np.array(response.data[0].embedding)

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def analyze_safety_text(text):
    global _rule_embs
    text_lower = text.lower()
    
    # Check for SIF Potential using keywords
    sif_potential = any(kw in text_lower for kw in SIF_KEYWORDS)
    
    matched_rule = "General Safety"
    
    api_key = current_app.config.get('OPENAI_API_KEY') or os.environ.get('OPENAI_API_KEY')
    
    if api_key:
        try:
            client = OpenAI(api_key=api_key)
            input_emb = get_openai_embedding(text, client)
            
            rules = list(rule_descriptions.keys())
            descriptions = list(rule_descriptions.values())
            
            # Cache the rule embeddings to save API calls
            if _rule_embs is None:
                _rule_embs = [get_openai_embedding(desc, client) for desc in descriptions]
                
            cos_scores = [cosine_similarity(input_emb, emb) for emb in _rule_embs]
            best_idx = np.argmax(cos_scores)
            
            if cos_scores[best_idx] > 0.4:  # Threshold for openai embeddings
                matched_rule = rules[best_idx]
        except Exception as e:
            print(f"OpenAI Embedding API failed: {e}")
            api_key = None # Fallback to keyword matching
            
    if not api_key:
        # Fallback to strict keyword matching if ML fails or API key missing
        for rule, keywords in IOGP_RULES.items():
            if any(kw in text_lower for kw in keywords):
                matched_rule = rule
                break

    # Determine Precursors and Hazards based on matched rule
    precursor = f"{matched_rule} Failure"
    if matched_rule == "Energy Isolation":
        activity = "Maintenance"
        hazard = "Unexpected Startup"
        barrier_failure = "Isolation not verified / LOTO missed"
    elif matched_rule == "Working at Height":
        activity = "Scaffolding / Roofing"
        hazard = "Fall from height"
        barrier_failure = "Fall protection missing"
    elif matched_rule == "Confined Space":
        activity = "Vessel Entry"
        hazard = "Toxic atmosphere"
        barrier_failure = "Gas testing not performed"
    elif matched_rule == "Line of Fire":
        activity = "Lifting / Moving"
        hazard = "Struck by object"
        barrier_failure = "Exclusion zone breached"
    elif matched_rule == "Hot Work":
        activity = "Welding / Cutting"
        hazard = "Fire / Explosion"
        barrier_failure = "Combustibles not cleared"
    else:
        activity = matched_rule + " Activity"
        hazard = matched_rule + " Hazard"
        barrier_failure = "Standard procedure not followed"
        
    return {
        "activity": activity,
        "hazard": hazard,
        "unsafe_condition": text,
        "precursor": precursor,
        "barrier_failure": barrier_failure,
        "life_saving_rule": matched_rule,
        "sif_potential": sif_potential
    }
