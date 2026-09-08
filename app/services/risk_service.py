# Risk scoring from NLP analysis output.

HIGH_RULES = {
    "Energy Isolation",
    "Working at Height",
    "Confined Space",
    "Line of Fire",
    "Hot Work",
    "Bypassing Safety Controls",
}


def calculate_sif_score(analysis_result):
    rule = analysis_result.get("life_saving_rule") or "General Safety"
    keyword_sif = bool(analysis_result.get("sif_potential", False))
    rule_sif = rule in HIGH_RULES

    if keyword_sif or rule_sif:
        score = 90 if keyword_sif and rule_sif else 80
        return {
            "score": score,
            "risk_level": "HIGH",
            "explanation": (
                f"SIF Potential identified. High risk of serious injury or fatality "
                f"related to {analysis_result.get('precursor') or rule}."
            ),
        }

    if rule != "General Safety":
        return {
            "score": 45,
            "risk_level": "MEDIUM",
            "explanation": (
                f"Life-Saving Rule signal detected ({rule}) without strong SIF keywords. "
                "Review recommended."
            ),
        }

    return {
        "score": 20,
        "risk_level": "LOW",
        "explanation": "No significant SIF precursor detected. Standard safety protocols apply.",
    }
