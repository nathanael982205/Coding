"""Theorie-Assistent, Methodik-Assistent, Studienvergleich und Forschungslücken.

Deterministischer Teil (Zuordnung, Belege, Zählungen) funktioniert ohne KI.
KI-Synthesen basieren ausschließlich auf den gespeicherten Analysen und werden
mit geprüften Zitationen gespeichert."""
from __future__ import annotations

from typing import Any

from . import db, llm, services
from .schema import CHAPTERS

METHOD_TOPICS: list[dict[str, Any]] = [
    {"key": "design", "title": "Forschungsdesign",
     "fields": [("design", "study_type"), ("design", "temporal_direction"), ("design", "duration"), ("design", "setting")]},
    {"key": "operationalization", "title": "Operationalisierung der Variablen",
     "fields": [("methods", "measured_parameters"), ("methods", "load_variable_definitions")], "variables": "all"},
    {"key": "cmj_parameters", "title": "Auswahl von CMJ-Kennwerten",
     "fields": [("methods", "cmj_device")], "variables": "cmj_neuromuscular"},
    {"key": "gps_parameters", "title": "Definition von GPS-Load-Parametern",
     "fields": [("methods", "gps_system"), ("methods", "load_variable_definitions")], "variables": "gps_external_load"},
    {"key": "recovery_timepoints", "title": "Auswahl von Erholungszeitpunkten",
     "fields": [("methods", "measurement_timing"), ("timepoints", "description"), ("design", "n_timepoints")]},
    {"key": "baselines", "title": "Individuelle Baselines",
     "fields": [("methods", "procedure"), ("methods", "measurement_timing")], "keywords": ["baseline", "individual", "swc", "smallest worthwhile", "z-score", "referenz"]},
    {"key": "repetitions", "title": "Messwiederholungen & Reliabilität",
     "fields": [("methods", "procedure"), ("methods", "instruments")], "keywords": ["trial", "versuch", "repetition", "wiederhol", "icc", "cv", "reliab", "best of", "mittelwert"]},
    {"key": "confounders", "title": "Potenzielle Confounder",
     "fields": [("methods", "confounders")]},
    {"key": "md1_compensation", "title": "MD+1-Kompensation",
     "fields": [("methods", "procedure"), ("timepoints", "description")], "keywords": ["md+1", "compensat", "kompensation", "substitut", "non-starter", "reserve", "recovery session"]},
    {"key": "missing_data", "title": "Fehlende Daten",
     "fields": [("methods", "statistical_methods")], "keywords": ["missing", "fehlend", "imput", "excluded", "dropout", "ausschluss"]},
    {"key": "statistics", "title": "Statistische Verfahren",
     "fields": [("methods", "statistical_methods"), ("statistics", "software"), ("statistics", "alpha_level")]},
    {"key": "mixed_models", "title": "Mixed-Effects-Modelle & wiederholte Messungen",
     "fields": [("methods", "repeated_measures_handling"), ("methods", "statistical_methods")], "keywords": ["mixed", "random", "linear mixed", "multilevel", "hierarch", "gee"]},
]
METHOD_TOPIC_KEYS = {t["key"]: t for t in METHOD_TOPICS}


def _get(a: dict[str, Any], path: tuple[str, str]) -> dict[str, Any] | None:
    node = (a.get(path[0]) or {}).get(path[1])
    return node if isinstance(node, dict) else None


def method_topic_evidence(key: str) -> dict[str, Any]:
    topic = METHOD_TOPIC_KEYS[key]
    kws = topic.get("keywords")
    items = []
    for row, a in services._analyses():
        entries = []
        for path in topic["fields"]:
            c = _get(a, path)
            if not c or c.get("status") == "not_reported":
                continue
            if kws and not any(k in (str(c.get("value", "")) + " " + str(c.get("quote", ""))).lower() for k in kws):
                continue
            entries.append({"field": ".".join(path), "value": c.get("value"), "page": c.get("page"),
                            "page_label": c.get("page_label"), "quote": c.get("quote"),
                            "status": c.get("status"), "source_type": c.get("source_type")})
        vcat = topic.get("variables")
        if vcat:
            for v in a.get("variables") or []:
                if vcat == "all" or v.get("category") == vcat:
                    entries.append({"field": "variables", "value": f"{v.get('name')}: {v.get('definition')}"
                                    + (f" [{v.get('unit')}]" if v.get("unit") else ""),
                                    "page": v.get("page"), "page_label": v.get("page_label"),
                                    "quote": v.get("quote"), "status": v.get("status"),
                                    "source_type": "author_statement"})
        if entries:
            items.append({"study_id": row["id"], "ref": services.short_ref(row), "title": row["title"],
                          "relevance": row["relevance_score"], "entries": entries})
    items.sort(key=lambda x: -(x["relevance"] or 0))
    note = db.get_conn().execute("SELECT content, updated_at FROM user_notes WHERE scope='method' AND key=?",
                                 (key,)).fetchone()
    return {"topic": {k: topic[k] for k in ("key", "title")}, "studies": items,
            "latest_ai": services.latest_ai_output("methods", key), "note": db.row_to_dict(note)}


def run_method_ai(key: str) -> dict[str, Any]:
    topic = METHOD_TOPIC_KEYS[key]
    ev = method_topic_evidence(key)
    ids = [s["study_id"] for s in ev["studies"]][:25]
    if not ids:
        raise ValueError("Keine analysierten Studien mit Angaben zu diesem Thema vorhanden.")
    rows = {r["id"]: (r, a) for r, a in services._analyses() if r["id"] in ids}
    digests = [services.digest(r, a) for r, a in rows.values()]
    task = (f"Methodik-Thema: „{topic['title']}“. 1) Fasse zusammen, welche methodischen Entscheidungen die "
            "importierten Studien zu diesem Thema getroffen haben (literature_finding, mit Belegen). "
            "2) Gib getrennt davon eigene, begründete Empfehlungen für die Masterarbeit (kind recommendation; "
            "citations nur, wenn eine Studie die Empfehlung stützt). 3) Liste offene Entscheidungen, die ich "
            "selbst treffen muss.")
    out, meta = llm.synthesize("methods", task, digests, llm.METHODS_SCHEMA, db.get_setting("thesis_context"))
    out = services.validate_citations(out, {i: rows[i][0] for i in rows})
    return services.save_ai_output("methods", key, list(rows), out, meta.get("model"))


def chapter_overview(key: str) -> dict[str, Any]:
    chapter = next(c for c in CHAPTERS if c["key"] == key)
    studies = services.studies_for_chapter(key)
    note = db.get_conn().execute("SELECT content, updated_at FROM user_notes WHERE scope='chapter' AND key=?",
                                 (key,)).fetchone()
    return {"chapter": chapter, "studies": studies, "latest_ai": services.latest_ai_output("theory", key),
            "note": db.row_to_dict(note)}


def run_chapter_ai(key: str, max_studies: int = 20) -> dict[str, Any]:
    chapter = next(c for c in CHAPTERS if c["key"] == key)
    studies = services.studies_for_chapter(key)[:max_studies]
    if not studies:
        raise ValueError("Diesem Kapitel sind noch keine analysierten Studien zugeordnet.")
    ids = {s["id"] for s in studies}
    rows = {r["id"]: (r, a) for r, a in services._analyses() if r["id"] in ids}
    digests = [services.digest(r, a) for r, a in rows.values()]
    task = (f"Theoriekapitel: „{chapter['title']}“.\n"
            "- prioritized_sources: die relevantesten Studien für dieses Kapitel mit Begründung.\n"
            "- key_insights: zentrale Erkenntnisse (literature_finding, belegt).\n"
            "- contradictions: widersprüchliche Ergebnisse zwischen Studien (belegt, beide Seiten zitieren).\n"
            "- argument_structure: mögliche Argumentationsstruktur als geordnete Schritte (ai_synthesis, mit Belegen).\n"
            "- draft_paragraphs: wissenschaftlicher Textentwurf (2–5 Absätze), jeder Satz mit Fakten ist belegt. "
            "Der Entwurf wird als KI-Entwurf gekennzeichnet und von mir geprüft.\n"
            "- missing_literature: Themen/Aspekte, zu denen in den importierten Studien Belege fehlen "
            "(keine konkreten Paper erfinden oder nennen).")
    out, meta = llm.synthesize("theory", task, digests, llm.THEORY_SCHEMA, db.get_setting("thesis_context"))
    out = services.validate_citations(out, {i: rows[i][0] for i in rows})
    for p in out.get("prioritized_sources") or []:
        p["ref"] = services.short_ref(rows[p["study_id"]][0]) if p.get("study_id") in rows else "Unbekannt"
    return services.save_ai_output("theory", key, list(rows), out, meta.get("model"))


COMPARE_DIMENSIONS = [
    ("research_question", "Forschungsfrage", ("design", "research_question")),
    ("design", "Forschungsdesign", ("design", "study_type")),
    ("participants", "Teilnehmer", ("sample", "n_participants")),
    ("level", "Leistungsniveau", ("sample", "performance_level")),
    ("gps", "GPS-Variablen", None),
    ("cmj", "CMJ-Parameter", None),
    ("timepoints", "Untersuchungszeitpunkte", ("methods", "measurement_timing")),
    ("statistics", "Statistische Methoden", ("methods", "statistical_methods")),
    ("findings", "Wichtigste Ergebnisse", None),
    ("limitations", "Limitationen", None),
    ("relevance", "Relevanz", None),
]


def compare_table(ids: list[int]) -> dict[str, Any]:
    rows = {r["id"]: (r, a) for r, a in services._analyses() if r["id"] in ids}
    missing = [i for i in ids if i not in rows]
    studies = []
    for i in ids:
        if i not in rows:
            continue
        r, a = rows[i]
        cells: dict[str, Any] = {}
        for key, _label, path in COMPARE_DIMENSIONS:
            if path:
                cells[key] = _get(a, path)
        vars_ = a.get("variables") or []
        cells["gps"] = {"items": sorted({services.canon(v.get("name", ""), services.GPS_CANON)[1]
                                         for v in vars_ if v.get("category") == "gps_external_load"}),
                        "raw": [v for v in vars_ if v.get("category") == "gps_external_load"]}
        cells["cmj"] = {"items": sorted({services.canon(v.get("name", ""), services.CMJ_CANON)[1]
                                         for v in vars_ if v.get("category") == "cmj_neuromuscular"}),
                        "raw": [v for v in vars_ if v.get("category") == "cmj_neuromuscular"]}
        cells["findings"] = (a.get("results") or {}).get("key_findings") or []
        cells["limitations"] = (a.get("critical") or {}).get("limitations_reported") or []
        cells["relevance"] = {"score": r["relevance_score"],
                              "recommendations": (a.get("relevance") or {}).get("recommendations")}
        cells["_categorical"] = {
            "design": (a.get("design") or {}).get("design_category"),
            "level": (a.get("sample") or {}).get("level_category"),
            "timepoints": sorted(m.upper() for m in (a.get("timepoints") or {}).get("md_offsets") or []),
            "statistics": sorted((a.get("statistics") or {}).get("method_tags") or []),
            "participants": (a.get("sample") or {}).get("sport_normalized"),
        }
        studies.append({"id": i, "ref": services.short_ref(r), "title": r["title"], "cells": cells})
    return {"dimensions": [{"key": k, "label": l} for k, l, _ in COMPARE_DIMENSIONS], "studies": studies,
            "missing": missing}


def run_compare_ai(ids: list[int]) -> dict[str, Any]:
    rows = {r["id"]: (r, a) for r, a in services._analyses() if r["id"] in ids}
    if len(rows) < 2:
        raise ValueError("Mindestens zwei analysierte Studien auswählen.")
    digests = [services.digest(r, a) for r, a in rows.values()]
    task = ("Vergleiche diese Studien: Was zeigen sie gemeinsam (commonalities), wo widersprechen sie sich "
            "(contradictions), welche methodischen Unterschiede gibt es (methodological_differences) und welche "
            "dieser Unterschiede könnten Widersprüche erklären (possible_explanations, kind ai_synthesis)? "
            "Nur auf Basis der gelieferten Analysen.")
    out, meta = llm.synthesize("compare", task, digests, llm.COMPARE_SCHEMA, db.get_setting("thesis_context"))
    out = services.validate_citations(out, {i: rows[i][0] for i in rows})
    key = "-".join(str(i) for i in sorted(rows))
    return services.save_ai_output("compare", key, sorted(rows), out, meta.get("model"))


def run_gaps_ai() -> dict[str, Any]:
    data = services._analyses()
    if len(data) < 2:
        raise ValueError("Für eine Lückenanalyse werden mindestens zwei analysierte Studien benötigt.")
    data.sort(key=lambda x: -(x[0]["relevance_score"] or 0))
    data = data[:40]
    rows = {r["id"]: (r, a) for r, a in data}
    digests = [services.digest(r, a, detail="short") for r, a in data]
    counts = services.gap_counts()
    compact_counts = {k: counts[k] for k in ("timepoints", "professional_football", "combos")}
    compact_counts = {k: ({kk: vv["count"] for kk, vv in v.items()} if k != "professional_football" else v["count"])
                      for k, v in compact_counts.items()}
    task = ("Vergleiche die importierte Literatur systematisch: gut untersuchte vs. selten untersuchte "
            "GPS- und CMJ-Parameter, Messzeitpunkte (24/48/72 h), Stichproben, widersprüchliche Ergebnisse, "
            "wiederkehrende methodische Einschränkungen. gaps_in_imported_literature: Lücken INNERHALB DER "
            "IMPORTIERTEN LITERATUR (keine Aussage über den gesamten Forschungsstand!). "
            "suggested_search_topics: Suchbegriffe/Themen für eine ergänzende systematische Recherche. "
            f"Deterministische Zählungen des Systems: {compact_counts}")
    out, meta = llm.synthesize("gaps", task, digests, llm.GAPS_SCHEMA, db.get_setting("thesis_context"))
    out = services.validate_citations(out, {i: rows[i][0] for i in rows})
    return services.save_ai_output("gaps", "all", list(rows), out, meta.get("model"))


def save_note(scope: str, key: str, content: str) -> dict[str, Any]:
    with db.tx() as c:
        c.execute("INSERT INTO user_notes(scope, key, content, updated_at) VALUES(?,?,?,?) "
                  "ON CONFLICT(scope, key) DO UPDATE SET content=excluded.content, updated_at=excluded.updated_at",
                  (scope, key, content, db.now_iso()))
    return {"scope": scope, "key": key, "content": content}
