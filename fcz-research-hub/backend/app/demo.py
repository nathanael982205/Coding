"""Klar gekennzeichnete DEMO-Daten für die leere Bibliothek.

Die Demo zeigt ausschließlich die STRUKTUR der Oberfläche. Alle Einträge sind
fiktiv, enthalten Platzhaltertexte statt wissenschaftlicher Aussagen und werden
weder gespeichert noch exportiert."""
from __future__ import annotations

from typing import Any

PH = "[Platzhalter – Demo] "


def _c(value: str, page: int = 0, status: str = "verified", source: str = "author_statement") -> dict[str, Any]:
    return {"value": PH + value, "page": page, "page_label": None, "quote": "", "status": status,
            "source_type": source, "check": {"quote_check": "no_quote", "note": "Demo-Daten"}}


def _study(i: int, year: int, design: str, gps: bool, cmj: bool, score: float, topics: list[str],
           chapters: list[str], level: str) -> dict[str, Any]:
    return {
        "id": -i, "demo": True, "filename": f"demo_studie_{i}.pdf", "status": "analyzed",
        "title": f"DEMO-Studie {i} (fiktiv) – Beispieltitel zur Darstellung",
        "authors": "Muster, A.; Beispiel, B.", "year": year, "journal": "Demo Journal (fiktiv)",
        "doi": None, "design_category": design, "sample_n": 10 + 4 * i, "level_category": level,
        "sport": "Fußball", "uses_gps": int(gps), "uses_cmj": int(cmj), "relevance_score": score,
        "short_summary": PH + "Hier erscheint die 3–5-sätzige KI-Zusammenfassung der importierten Studie.",
        "topics": topics, "chapters": chapters, "recommendations": ["theory_background"],
        "stat_methods": ["mixed_models"] if i % 2 else ["correlation"],
        "flags": {"uses_gps": gps, "uses_cmj": cmj},
        "timepoints": {"covers_24h": True, "covers_48h": i % 2 == 0, "covers_72h": i == 3, "md_offsets": ["MD+1"]},
        "gps_variables": ["High-Speed Running", "Total Distance"] if gps else [],
        "cmj_variables": ["Sprunghöhe", "FT:CT"] if cmj else [],
        "user_tags": [], "text_quality": {"overall": "ok"}, "page_count": 10, "has_notes": 0,
        "verification": None, "chapter_override": None,
    }


def demo_payload() -> dict[str, Any]:
    studies = [
        _study(1, 2019, "observational_longitudinal", True, True, 82, ["cmj", "external_load", "post_match_recovery"],
               ["load_cmj_relationship", "post_match_recovery"], "professional"),
        _study(2, 2021, "reliability_validity", False, True, 64, ["cmj", "reliability_validity"],
               ["cmj_monitoring"], "semi_professional"),
        _study(3, 2022, "observational_longitudinal", True, False, 55, ["gps_monitoring", "match_load"],
               ["external_load_gps"], "professional"),
        _study(4, 2023, "systematic_review", True, True, 71, ["neuromuscular_fatigue", "readiness"],
               ["neuromuscular_fatigue", "load_monitoring"], "not_applicable"),
    ]
    analysis = {
        "summary": {"short_summary": studies[0]["short_summary"], "what_was_studied": _c("Untersuchungsgegenstand", 1)},
        "bibliographic": {k: _c(v) for k, v in (("title", "Titel"), ("authors", "Autoren"), ("year", "Jahr"), ("journal", "Journal"), ("doi", "DOI"), ("keywords", "Keywords"), ("research_field", "Forschungsgebiet"))},
        "design": {"research_question": _c("Forschungsfrage mit Seitenbeleg", 2),
                   "hypotheses": _c("Nicht berichtet", 0, "not_reported"),
                   "study_type": _c("Studientyp", 3), "design_category": "observational_longitudinal",
                   "temporal_direction": _c("Prospektiv/retrospektiv", 3), "duration": _c("Dauer", 3),
                   "n_timepoints": _c("Anzahl Messzeitpunkte", 3), "control_condition": _c("Vergleichsbedingung", 3),
                   "setting": _c("Setting", 3)},
        "sample": {"n_participants": _c("Teilnehmende", 3), "n_numeric": 14, "age": _c("Alter", 3),
                   "sex": _c("Geschlecht", 3), "performance_level": _c("Leistungsniveau", 3),
                   "level_category": "professional", "sport": _c("Sportart", 3), "sport_normalized": "Fußball",
                   "inclusion_exclusion": _c("Kriterien", 3, "uncertain")},
        "methods": {k: _c(k.replace("_", " ").capitalize(), 4) for k in (
            "instruments", "gps_system", "cmj_device", "measured_parameters", "load_variable_definitions",
            "measurement_timing", "procedure", "statistical_methods", "repeated_measures_handling", "confounders")},
        "variables": [
            {"name": "High-Speed Running (Demo)", "category": "gps_external_load", "definition": PH + "Schwellenwert",
             "unit": "m", "device": "GPS", "page": 4, "page_label": None, "quote": "", "status": "verified",
             "check": {"quote_check": "no_quote"}},
            {"name": "CMJ-Sprunghöhe (Demo)", "category": "cmj_neuromuscular", "definition": PH + "Berechnungsmethode",
             "unit": "cm", "device": "Kraftmessplatte", "page": 4, "page_label": None, "quote": "",
             "status": "verified", "check": {"quote_check": "no_quote"}},
        ],
        "results": {"key_findings": [_c("Wichtigstes Ergebnis 1", 6), _c("Wichtigstes Ergebnis 2", 7, "uncertain")],
                    "effect_sizes": [_c("Effektgröße", 6)], "correlations": [], "confidence_intervals": [],
                    "significance": [], "timepoint_differences": [_c("Unterschied MD+1 vs. Baseline", 7)],
                    "practical_significance": _c("Praktische Bedeutung", 8, "verified", "ai_summary"),
                    "fatigue_recovery_statements": [_c("Aussage zur Erholung", 8)]},
        "statistics": {"method_tags": ["mixed_models"], "software": _c("Software", 5), "alpha_level": _c("Alpha", 5)},
        "timepoints": {"description": _c("Messzeitpunkte", 4), "covers_24h": True, "covers_48h": False,
                       "covers_72h": False, "md_offsets": ["MD+1"]},
        "flags": {"uses_gps": True, "uses_cmj": True, "football": True, "professional_football": True,
                  "internal_load": False, "force_time_parameters": True},
        "critical": {"strengths": [_c("Stärke", 0, "verified", "ai_assessment")],
                     "weaknesses": [_c("Methodische Schwäche", 0, "verified", "ai_assessment")],
                     "limitations_reported": [_c("Limitation laut Autoren", 9)],
                     "transferability": _c("Übertragbarkeit", 0, "verified", "ai_assessment"),
                     "comparability_to_thesis": _c("Vergleichbarkeit", 0, "verified", "ai_assessment"),
                     "open_questions": [_c("Offene Frage", 0, "verified", "ai_assessment")]},
        "relevance": {k: {"score": s, "rationale": PH + "Begründung"} for k, s in
                      (("thematic", 90), ("methodological", 80), ("sample", 85), ("variables", 80), ("theoretical", 60))}
        | {"overall_rationale": PH + "Gesamtbegründung", "recommendations": ["theory_background"],
           "chapters": ["load_cmj_relationship"]},
        "topics": studies[0]["topics"], "page_numbering_note": PH + "Seitenhinweis",
        "verification": None, "meta": {"relevance_total": 82, "model": "demo"},
    }
    stats = {
        "total": 4, "analyzed": 4, "high_relevance": 2, "with_cmj": 3, "with_gps": 3, "needs_ocr": 0, "errors": 0,
        "pending": 0, "by_year": {2019: 1, 2021: 1, 2022: 1, 2023: 1},
        "by_design": {"Beobachtung – longitudinal": 2, "Reliabilitäts-/Validitätsstudie": 1, "Systematisches Review": 1},
        "topics": {"cmj": 2, "external_load": 1, "post_match_recovery": 1, "reliability_validity": 1,
                   "gps_monitoring": 1, "match_load": 1, "neuromuscular_fatigue": 1, "readiness": 1},
        "variables": {"Sprunghöhe": 3, "FT:CT": 3, "High-Speed Running": 3, "Total Distance": 3},
        "relevance_bins": {"0–9": 0, "10–19": 0, "20–29": 0, "30–39": 0, "40–49": 0, "50–59": 1, "60–69": 1,
                           "70–79": 1, "80–89": 1, "90–100": 0},
        "chapters": {},
    }
    return {"demo": True, "notice": "DEMO – fiktive Beispieldaten zur Veranschaulichung der Oberfläche. "
                                    "Keine echten Studien, keine wissenschaftlichen Aussagen.",
            "studies": studies, "stats": stats, "analysis": analysis}
