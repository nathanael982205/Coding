"""Strukturiertes Analyseschema, feste Vokabulare (Kapitel, Themen, Designs) und
Relevanzgewichtung. Jede inhaltliche Angabe ist ein "Claim" mit Seitenbeleg."""
from __future__ import annotations

from typing import Any

CHAPTERS: list[dict[str, str]] = [
    {"key": "load_monitoring", "title": "Belastungsmonitoring im professionellen Fußball"},
    {"key": "external_load_gps", "title": "External Load und GPS-basierte Messmethoden"},
    {"key": "neuromuscular_fatigue", "title": "Neuromuskuläre Ermüdung und Readiness"},
    {"key": "cmj_monitoring", "title": "Countermovement Jump als Monitoringinstrument"},
    {"key": "post_match_recovery", "title": "Erholung nach Spielbelastungen"},
    {"key": "load_cmj_relationship", "title": "Zusammenhang zwischen External Load und CMJ"},
    {"key": "gaps_hypotheses", "title": "Forschungslücken und Hypothesen"},
]
CHAPTER_KEYS = [c["key"] for c in CHAPTERS]

RECOMMENDATIONS = {
    "theory_background": "Besonders geeignet für den theoretischen Hintergrund",
    "methods_justification": "Besonders geeignet zur Begründung der Methodik",
    "results_interpretation": "Relevant für die Interpretation der Ergebnisse",
    "limited_relevance": "Nur eingeschränkt relevant",
    "not_directly_relevant": "Nicht unmittelbar relevant",
}

TOPICS = {
    "neuromuscular_fatigue": "Neuromuskuläre Ermüdung",
    "readiness": "Readiness",
    "cmj": "Countermovement Jump",
    "force_time": "Force-Time-Parameter",
    "external_load": "External Load",
    "gps_monitoring": "GPS-Monitoring",
    "high_speed_sprint": "High-Speed Running / Sprint",
    "acc_dec": "Accelerations / Decelerations",
    "match_load": "Match Load",
    "training_load": "Training Load",
    "post_match_recovery": "Post-Match Recovery",
    "individual_baseline": "Individuelle Baselines",
    "wellness_rpe": "Wellness / RPE / Internal Load",
    "reliability_validity": "Reliabilität & Validität",
    "repeated_measures_stats": "Statistik wiederholter Messungen",
    "biochemical_markers": "Biochemische Marker",
    "injury": "Verletzungen",
    "other": "Sonstiges",
}

DESIGN_CATEGORIES = {
    "experimental": "Experimentell (randomisiert/kontrolliert)",
    "quasi_experimental": "Quasi-experimentell",
    "observational_longitudinal": "Beobachtung – longitudinal",
    "observational_cross_sectional": "Beobachtung – Querschnitt",
    "reliability_validity": "Reliabilitäts-/Validitätsstudie",
    "systematic_review": "Systematisches Review",
    "meta_analysis": "Meta-Analyse",
    "narrative_review": "Narratives Review",
    "case_study": "Fallstudie",
    "other": "Sonstiges",
    "not_reported": "Nicht berichtet",
}

LEVEL_CATEGORIES = {
    "professional": "Professionell",
    "semi_professional": "Semi-professionell",
    "youth_elite": "Elite-Nachwuchs",
    "amateur": "Amateur",
    "recreational": "Freizeit",
    "mixed": "Gemischt",
    "not_applicable": "Nicht zutreffend (z. B. Review)",
    "not_reported": "Nicht berichtet",
}

STAT_METHODS = {
    "descriptive": "Deskriptiv",
    "t_test": "t-Test",
    "anova": "ANOVA",
    "anova_rm": "ANOVA mit Messwiederholung",
    "correlation": "Korrelation",
    "regression": "Regression",
    "mixed_models": "Mixed-Effects-Modelle",
    "gee": "GEE",
    "magnitude_based": "Magnitude-based / SWC",
    "bayesian": "Bayes",
    "reliability_stats": "Reliabilität (ICC/CV/TE)",
    "meta_analysis": "Meta-analytisch",
    "nonparametric": "Nicht-parametrisch",
    "machine_learning": "Machine Learning",
    "other": "Sonstiges",
}

VARIABLE_CATEGORIES = {
    "gps_external_load": "GPS / External Load",
    "cmj_neuromuscular": "CMJ / neuromuskulär",
    "other_neuromuscular": "Andere neuromuskuläre Tests",
    "internal_load": "Internal Load (RPE, HF)",
    "wellness": "Wellness / Fragebogen",
    "biochemical": "Biochemisch",
    "other": "Sonstiges",
}

SOURCE_TYPES = {
    "author_statement": "Aussage der Autoren",
    "ai_summary": "KI-Zusammenfassung",
    "ai_assessment": "KI-Bewertung",
}

RELEVANCE_WEIGHTS = {
    "thematic": 0.30,
    "methodological": 0.25,
    "sample": 0.15,
    "variables": 0.20,
    "theoretical": 0.10,
}
RELEVANCE_LABELS = {
    "thematic": "Thematische Übereinstimmung",
    "methodological": "Methodische Vergleichbarkeit",
    "sample": "Vergleichbarkeit der Stichprobe",
    "variables": "Relevanz der untersuchten Variablen",
    "theoretical": "Bedeutung für die theoretische Argumentation",
}

NOT_REPORTED = "Nicht berichtet"


def _claim() -> dict[str, Any]:
    return {"$ref": "#/$defs/claim"}


def _claims() -> dict[str, Any]:
    return {"type": "array", "items": {"$ref": "#/$defs/claim"}}


def _obj(props: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": list(props.keys()),
            "additionalProperties": False}


def _enum(values) -> dict[str, Any]:
    return {"type": "string", "enum": list(values)}


CLAIM_DEF = _obj({
    "value": {"type": "string", "description": "Inhaltliche Angabe auf Deutsch. 'Nicht berichtet', falls im Dokument nicht vorhanden."},
    "page": {"type": "integer", "description": "Physische PDF-Seite (1-basiert, gemäß [[PDF-SEITE n]] Markern). 0 falls nicht zutreffend."},
    "quote": {"type": "string", "description": "Wörtliches, unverändertes Zitat (Originalsprache, 5–40 Wörter) aus genau dieser Seite. Leer, falls nicht berichtet oder reine KI-Bewertung."},
    "status": _enum(["verified", "uncertain", "not_reported"]),
    "source_type": _enum(list(SOURCE_TYPES)),
})

VARIABLE_DEF = _obj({
    "name": {"type": "string"},
    "category": _enum(list(VARIABLE_CATEGORIES)),
    "definition": {"type": "string", "description": "Definition inkl. Schwellenwerte (z. B. >19,8 km/h), sonst 'Nicht berichtet'."},
    "unit": {"type": "string"},
    "device": {"type": "string"},
    "page": {"type": "integer"},
    "quote": {"type": "string"},
    "status": _enum(["verified", "uncertain", "not_reported"]),
})

SCORE_DEF = _obj({
    "score": {"type": "integer", "description": "0–100"},
    "rationale": {"type": "string"},
})

ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "$defs": {"claim": CLAIM_DEF, "variable": VARIABLE_DEF, "score": SCORE_DEF},
    "properties": {
        "summary": _obj({
            "short_summary": {"type": "string", "description": "3–5 Sätze, KI-Zusammenfassung auf Deutsch."},
            "what_was_studied": _claim(),
        }),
        "bibliographic": _obj({
            "title": _claim(), "authors": _claim(), "year": _claim(), "journal": _claim(),
            "doi": _claim(), "keywords": _claim(), "research_field": _claim(),
        }),
        "design": _obj({
            "research_question": _claim(),
            "hypotheses": _claim(),
            "study_type": _claim(),
            "design_category": _enum(list(DESIGN_CATEGORIES)),
            "temporal_direction": _claim(),
            "duration": _claim(),
            "n_timepoints": _claim(),
            "control_condition": _claim(),
            "setting": _claim(),
        }),
        "sample": _obj({
            "n_participants": _claim(),
            "n_numeric": {"type": "integer", "description": "Gesamtzahl Teilnehmende als Zahl; 0 falls nicht berichtet/Review."},
            "age": _claim(),
            "sex": _claim(),
            "performance_level": _claim(),
            "level_category": _enum(list(LEVEL_CATEGORIES)),
            "sport": _claim(),
            "sport_normalized": {"type": "string", "description": "Kurzform, z. B. 'Fußball', 'Rugby', 'Mehrere', 'Nicht berichtet'"},
            "inclusion_exclusion": _claim(),
        }),
        "methods": _obj({
            "instruments": _claim(),
            "gps_system": _claim(),
            "cmj_device": _claim(),
            "measured_parameters": _claim(),
            "load_variable_definitions": _claim(),
            "measurement_timing": _claim(),
            "procedure": _claim(),
            "statistical_methods": _claim(),
            "repeated_measures_handling": _claim(),
            "confounders": _claim(),
        }),
        "variables": {"type": "array", "items": {"$ref": "#/$defs/variable"}},
        "results": _obj({
            "key_findings": _claims(),
            "effect_sizes": _claims(),
            "correlations": _claims(),
            "confidence_intervals": _claims(),
            "significance": _claims(),
            "timepoint_differences": _claims(),
            "practical_significance": _claim(),
            "fatigue_recovery_statements": _claims(),
        }),
        "statistics": _obj({
            "method_tags": {"type": "array", "items": _enum(list(STAT_METHODS))},
            "software": _claim(),
            "alpha_level": _claim(),
        }),
        "timepoints": _obj({
            "description": _claim(),
            "covers_24h": {"type": "boolean"},
            "covers_48h": {"type": "boolean"},
            "covers_72h": {"type": "boolean"},
            "md_offsets": {"type": "array", "items": {"type": "string"}, "description": "z. B. 'MD-1','MD+1','MD+2'"},
        }),
        "flags": _obj({
            "uses_gps": {"type": "boolean"},
            "uses_cmj": {"type": "boolean"},
            "football": {"type": "boolean"},
            "professional_football": {"type": "boolean"},
            "internal_load": {"type": "boolean"},
            "force_time_parameters": {"type": "boolean"},
        }),
        "critical": _obj({
            "strengths": _claims(),
            "weaknesses": _claims(),
            "limitations_reported": _claims(),
            "transferability": _claim(),
            "comparability_to_thesis": _claim(),
            "open_questions": _claims(),
        }),
        "relevance": _obj({
            "thematic": {"$ref": "#/$defs/score"},
            "methodological": {"$ref": "#/$defs/score"},
            "sample": {"$ref": "#/$defs/score"},
            "variables": {"$ref": "#/$defs/score"},
            "theoretical": {"$ref": "#/$defs/score"},
            "overall_rationale": {"type": "string"},
            "recommendations": {"type": "array", "items": _enum(list(RECOMMENDATIONS))},
            "chapters": {"type": "array", "items": _enum(CHAPTER_KEYS)},
        }),
        "topics": {"type": "array", "items": _enum(list(TOPICS))},
        "page_numbering_note": {"type": "string", "description": "Hinweis zum Verhältnis physische vs. gedruckte Seitenzahl."},
    },
}
ANALYSIS_SCHEMA["required"] = list(ANALYSIS_SCHEMA["properties"].keys())
ANALYSIS_SCHEMA["additionalProperties"] = False


def compute_relevance(rel: dict[str, Any]) -> float | None:
    """Gewichteter Gesamtscore (deterministisch im Backend berechnet)."""
    if not rel:
        return None
    total = 0.0
    for key, w in RELEVANCE_WEIGHTS.items():
        sub = rel.get(key) or {}
        try:
            s = max(0, min(100, int(sub.get("score", 0))))
        except (TypeError, ValueError):
            s = 0
        total += w * s
    return round(total, 1)


def vocab() -> dict[str, Any]:
    return {
        "chapters": CHAPTERS,
        "recommendations": RECOMMENDATIONS,
        "topics": TOPICS,
        "design_categories": DESIGN_CATEGORIES,
        "level_categories": LEVEL_CATEGORIES,
        "stat_methods": STAT_METHODS,
        "variable_categories": VARIABLE_CATEGORIES,
        "source_types": SOURCE_TYPES,
        "relevance_weights": RELEVANCE_WEIGHTS,
        "relevance_labels": RELEVANCE_LABELS,
        "user_tags": {
            "very_important": "Sehr wichtig",
            "relevant": "Relevant",
            "read_later": "Später lesen",
            "read": "Gelesen",
            "for_methods": "Für Methodik verwenden",
            "for_discussion": "Für Diskussion verwenden",
        },
    }
