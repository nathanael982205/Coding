"""Fachlogik: Import, Analyse anwenden, Suche, Kennzahlen, Vergleich, Lückenanalyse."""
from __future__ import annotations

import hashlib
import logging
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from . import config, db, llm
from .pdf_processing import extract_pdf, heuristic_scan, sanitize_filename
from .schema import (CHAPTERS, DESIGN_CATEGORIES, LEVEL_CATEGORIES, STAT_METHODS,
                     compute_relevance)
from .verification import evidence_rows, is_not_reported, verify_analysis

log = logging.getLogger("research_hub.services")

SUMMARY_COLUMNS = (
    "id, filename, file_size, page_count, imported_at, status, status_message, text_quality, "
    "heuristics, title, authors, year, journal, doi, design_category, sample_n, level_category, "
    "sport, uses_gps, uses_cmj, relevance_score, short_summary, analysis_model, analyzed_at, "
    "user_tags, chapter_override, (notes <> '') AS has_notes"
)

# Normalisierung von Variablennamen für Häufigkeits-/Lückenanalysen (Reihenfolge = Priorität)
GPS_CANON: list[tuple[str, str, list[str]]] = [
    ("total_distance", "Total Distance", ["total distance", "distance covered", "total running distance", "td "]),
    ("hsr", "High-Speed Running", ["high-speed", "high speed", "hsr", "high-intensity running", "high intensity running", "hir"]),
    ("sprint", "Sprint Distance/Anzahl", ["sprint"]),
    ("acc", "Accelerations", ["acceleration", "acc"]),
    ("dec", "Decelerations", ["deceleration", "dec"]),
    ("playerload", "PlayerLoad / Accelerometer Load", ["playerload", "player load", "body load", "accelerometer"]),
    ("metabolic", "Metabolic Power / HMLD", ["metabolic", "hmld", "high metabolic"]),
    ("max_speed", "Maximalgeschwindigkeit", ["max speed", "maximal speed", "peak speed", "maximum velocity", "peak velocity", "vmax"]),
    ("relative_distance", "Relative Distanz (m/min)", ["m/min", "m·min", "per minute", "relative distance"]),
    ("impacts", "Impacts / Jumps", ["impact", "jump"]),
    ("duration", "Dauer / Exposure", ["duration", "minutes played", "playing time"]),
]
CMJ_CANON: list[tuple[str, str, list[str]]] = [
    ("ft_ct", "FT:CT", ["ft:ct", "ft/ct", "flight time:contraction", "flight time to contraction"]),
    ("rsimod", "RSImod", ["rsi", "reactive strength"]),
    ("jump_height", "Sprunghöhe", ["jump height", "height", "cmj performance", "cmjh"]),
    ("contraction_time", "Contraction Time / Time to Take-off", ["contraction time", "time to take", "time-to-take"]),
    ("flight_time", "Flugzeit", ["flight time"]),
    ("peak_power", "Peak Power", ["peak power", "power"]),
    ("peak_force", "Peak Force", ["peak force", "peak concentric force", "peak propulsive force", "force at"]),
    ("concentric", "Konzentrische Parameter (Impuls/Kraft)", ["concentric", "propulsive"]),
    ("eccentric", "Exzentrische Parameter (Impuls/RFD)", ["eccentric", "braking", "deceleration rfd", "unweighting"]),
    ("rfd", "Rate of Force Development", ["rfd", "rate of force"]),
    ("velocity", "Take-off Velocity", ["velocity"]),
    ("cm_depth", "Countermovement Depth", ["depth", "displacement"]),
    ("landing", "Landing-Parameter", ["landing"]),
]


def canon(name: str, table: list[tuple[str, str, list[str]]]) -> tuple[str, str]:
    n = " " + (name or "").lower() + " "
    for key, label, terms in table:
        if any(t in n for t in terms):
            return key, label
    return "other", (name or "Sonstige").strip()[:60]


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def import_pdf(filename: str, content: bytes) -> dict[str, Any]:
    """Speichert ein PDF, erkennt Dubletten, extrahiert Text. Gibt Ergebnisdict zurück."""
    original = Path(filename or "dokument.pdf").name
    if not content:
        return {"filename": original, "result": "error", "message": "Leere Datei."}
    if not content[:1024].lstrip().startswith(b"%PDF"):
        return {"filename": original, "result": "error", "message": "Keine gültige PDF-Datei (PDF-Signatur fehlt)."}
    sha = hashlib.sha256(content).hexdigest()
    conn = db.get_conn()
    dup = conn.execute("SELECT id, filename, title FROM studies WHERE sha256=?", (sha,)).fetchone()
    if dup:
        return {"filename": original, "result": "duplicate", "study_id": dup["id"],
                "message": f"Bereits importiert als „{dup['title'] or dup['filename']}“ (identischer Inhalt)."}

    stored = sanitize_filename(original)
    base, ext = stored[:-4], stored[-4:]
    i = 1
    while (config.PDF_DIR / stored).exists() or conn.execute(
            "SELECT 1 FROM studies WHERE stored_name=?", (stored,)).fetchone():
        i += 1
        stored = f"{base} ({i}){ext}"
    path = config.PDF_DIR / stored
    path.write_bytes(content)

    try:
        extracted = extract_pdf(path)
    except ValueError as exc:
        path.unlink(missing_ok=True)
        return {"filename": original, "result": "error", "message": str(exc)}

    pages = extracted["pages"]
    tq = extracted["text_quality"]
    heur = heuristic_scan(pages, extracted["metadata"])
    status = "needs_ocr" if tq["overall"] == "needs_ocr" else "extracted"
    msg = tq["hint"]

    # Mögliche inhaltliche Dublette über DOI (z. B. andere PDF-Version derselben Studie)
    doi_dup = None
    if heur.get("doi"):
        r = conn.execute("SELECT id, filename FROM studies WHERE lower(doi)=lower(?) OR "
                         "lower(json_extract(heuristics,'$.doi'))=lower(?)", (heur["doi"], heur["doi"])).fetchone()
        if r:
            doi_dup = {"study_id": r["id"], "filename": r["filename"]}

    with db.tx() as c:
        cur = c.execute(
            "INSERT INTO studies(filename, stored_name, sha256, file_size, page_count, imported_at, "
            "status, status_message, text_quality, pdf_metadata, heuristics, title, doi) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (original, stored, sha, len(content), len(pages), db.now_iso(), status, msg,
             db.dumps(tq), db.dumps(extracted["metadata"]), db.dumps(heur),
             heur.get("title_from_metadata"), heur.get("doi")),
        )
        sid = cur.lastrowid
        c.executemany(
            "INSERT INTO pages(study_id, page_number, page_label, label_source, text, char_count, quality) "
            "VALUES(?,?,?,?,?,?,?)",
            [(sid, p["page_number"], p["page_label"], p["label_source"], p["text"], p["char_count"], p["quality"])
             for p in pages],
        )
        c.executemany("INSERT INTO pages_fts(text, study_id, page_number) VALUES(?,?,?)",
                      [(p["text"], sid, p["page_number"]) for p in pages if p["text"].strip()])
    _refresh_study_fts(sid)
    res = {"filename": original, "stored_name": stored, "result": "imported", "study_id": sid,
           "status": status, "text_quality": tq, "message": msg}
    if doi_dup:
        res["possible_duplicate"] = doi_dup
        res["message"] = (f"Achtung: gleiche DOI wie „{doi_dup['filename']}“ – möglicherweise andere Version derselben Studie. "
                          + msg)
    return res


def get_pages(study_id: int) -> list[dict[str, Any]]:
    rows = db.get_conn().execute(
        "SELECT page_number, page_label, label_source, text, char_count, quality FROM pages "
        "WHERE study_id=? ORDER BY page_number", (study_id,)).fetchall()
    return [db.row_to_dict(r) for r in rows]


def get_study_row(study_id: int) -> dict[str, Any] | None:
    return db.row_to_dict(db.get_conn().execute("SELECT * FROM studies WHERE id=?", (study_id,)).fetchone())


# ---------------------------------------------------------------------------
# Analyse
# ---------------------------------------------------------------------------

def _claim_value(analysis: dict[str, Any], *path: str) -> str | None:
    node: Any = analysis
    for p in path:
        if not isinstance(node, dict):
            return None
        node = node.get(p)
    if isinstance(node, dict):
        v = str(node.get("value", "")).strip()
        return None if is_not_reported(v) else v
    return None


def _parse_year(v: str | None) -> int | None:
    if not v:
        return None
    m = re.search(r"\b(19[5-9]\d|20[0-4]\d)\b", v)
    return int(m.group(1)) if m else None


def run_analysis(study_id: int) -> None:
    """Führt die KI-Analyse aus und speichert das verifizierte Ergebnis."""
    row = get_study_row(study_id)
    if not row:
        return
    pages = get_pages(study_id)
    tq = db.loads(row["text_quality"], {})
    if tq.get("overall") == "needs_ocr":
        _set_status(study_id, "needs_ocr", tq.get("hint"))
        return
    _set_status(study_id, "analyzing", "KI-Analyse läuft …")
    try:
        analysis, meta = llm.analyze_study(row["filename"], pages, db.loads(row["heuristics"], {}),
                                           db.get_setting("thesis_context"))
    except llm.AIUnavailable as exc:
        _set_status(study_id, "no_api", str(exc))
        return
    except Exception as exc:  # noqa: BLE001
        log.exception("Analyse fehlgeschlagen (Studie %s)", study_id)
        _set_status(study_id, "error", f"Analyse fehlgeschlagen: {exc}")
        return
    save_analysis(study_id, analysis, meta, pages)


def save_analysis(study_id: int, analysis: dict[str, Any], meta: dict[str, Any],
                  pages: list[dict[str, Any]] | None = None) -> None:
    pages = pages if pages is not None else get_pages(study_id)
    verify_analysis(analysis, pages)
    rel = analysis.get("relevance") or {}
    score = compute_relevance(rel)
    analysis.setdefault("meta", {})
    analysis["meta"].update({
        "model": meta.get("model"),
        "omitted_pages": meta.get("omitted_pages", []),
        "relevance_total": score,
        "relevance_formula": "0,30·Thematik + 0,25·Methodik + 0,15·Stichprobe + 0,20·Variablen + 0,10·Theorie",
    })
    flags = analysis.get("flags") or {}
    sample = analysis.get("sample") or {}
    n = sample.get("n_numeric")
    with db.tx() as c:
        c.execute(
            "UPDATE studies SET status='analyzed', status_message=?, title=COALESCE(?, title), authors=?, "
            "year=?, journal=?, doi=COALESCE(?, doi), design_category=?, sample_n=?, level_category=?, "
            "sport=?, uses_gps=?, uses_cmj=?, relevance_score=?, short_summary=?, analysis_json=?, "
            "analysis_model=?, analyzed_at=?, analysis_usage=? WHERE id=?",
            (
                _analysis_message(analysis),
                _claim_value(analysis, "bibliographic", "title"),
                _claim_value(analysis, "bibliographic", "authors"),
                _parse_year(_claim_value(analysis, "bibliographic", "year")),
                _claim_value(analysis, "bibliographic", "journal"),
                _claim_value(analysis, "bibliographic", "doi"),
                (analysis.get("design") or {}).get("design_category"),
                n if isinstance(n, int) and n > 0 else None,
                sample.get("level_category"),
                sample.get("sport_normalized"),
                1 if flags.get("uses_gps") else 0,
                1 if flags.get("uses_cmj") else 0,
                score,
                (analysis.get("summary") or {}).get("short_summary"),
                db.dumps(analysis),
                meta.get("model"),
                db.now_iso(),
                db.dumps({k: meta.get(k) for k in ("input_tokens", "output_tokens", "structured_output")}),
                study_id,
            ),
        )
        c.execute("DELETE FROM evidence WHERE study_id=?", (study_id,))
        c.executemany(
            "INSERT INTO evidence(study_id, field_path, statement, page, page_label, quote, status, "
            "source_type, quote_check) VALUES(?,?,?,?,?,?,?,?,?)", evidence_rows(study_id, analysis))
    _refresh_study_fts(study_id)


def _analysis_message(analysis: dict[str, Any]) -> str:
    v = analysis.get("verification") or {}
    msg = (f"Analysiert. {v.get('claims', 0)} Angaben: {v.get('verified', 0)} verifiziert, "
           f"{v.get('uncertain', 0)} unsicher, {v.get('not_reported', 0)} nicht berichtet. "
           f"Zitate: {v.get('quote_exact', 0)} wörtlich, {v.get('quote_fuzzy', 0)} nahezu wörtlich, "
           f"{v.get('quote_not_found', 0)} nicht gefunden.")
    om = (analysis.get("meta") or {}).get("omitted_pages")
    if om:
        msg += f" Achtung: Seiten {om} wegen Längenlimit nicht analysiert."
    return msg


def _set_status(study_id: int, status: str, message: str | None) -> None:
    with db.tx() as c:
        c.execute("UPDATE studies SET status=?, status_message=? WHERE id=?", (status, message, study_id))


def _refresh_study_fts(study_id: int) -> None:
    row = get_study_row(study_id)
    if not row:
        return
    parts = [row.get("filename") or "", row.get("title") or "", row.get("authors") or "",
             row.get("journal") or "", row.get("short_summary") or "", row.get("notes") or ""]
    analysis = db.loads(row.get("analysis_json"), None)
    if analysis:
        from .verification import iter_claims
        for _, c in iter_claims(analysis):
            parts.append(str(c.get("value", "")))
        for v in analysis.get("variables", []) or []:
            parts.append(f"{v.get('name', '')} {v.get('definition', '')}")
    with db.tx() as c:
        c.execute("DELETE FROM studies_fts WHERE study_id=?", (study_id,))
        c.execute("INSERT INTO studies_fts(content, study_id) VALUES(?,?)", ("\n".join(parts), study_id))


def delete_study(study_id: int) -> bool:
    row = get_study_row(study_id)
    if not row:
        return False
    with db.tx() as c:
        c.execute("DELETE FROM pages_fts WHERE study_id=?", (study_id,))
        c.execute("DELETE FROM studies_fts WHERE study_id=?", (study_id,))
        c.execute("DELETE FROM studies WHERE id=?", (study_id,))
    (config.PDF_DIR / row["stored_name"]).unlink(missing_ok=True)
    return True


# ---------------------------------------------------------------------------
# Abfragen
# ---------------------------------------------------------------------------

def list_studies() -> list[dict[str, Any]]:
    rows = db.get_conn().execute(f"SELECT {SUMMARY_COLUMNS}, analysis_json FROM studies ORDER BY id DESC").fetchall()
    out = []
    for r in rows:
        d = db.row_to_dict(r)
        a = db.loads(d.pop("analysis_json"), None)
        d["text_quality"] = db.loads(d["text_quality"], {})
        d["heuristics"] = db.loads(d["heuristics"], {})
        d["user_tags"] = db.loads(d["user_tags"], [])
        d["chapter_override"] = db.loads(d["chapter_override"], None)
        d.update(_derived(a))
        if d["chapter_override"] is not None:
            d["chapters"] = d["chapter_override"]
        out.append(d)
    return out


def _derived(a: dict[str, Any] | None) -> dict[str, Any]:
    if not a:
        return {"topics": [], "chapters": [], "recommendations": [], "stat_methods": [],
                "flags": {}, "timepoints": {}, "gps_variables": [], "cmj_variables": [],
                "verification": None}
    vars_ = a.get("variables") or []
    tp = a.get("timepoints") or {}
    return {
        "topics": a.get("topics") or [],
        "chapters": (a.get("relevance") or {}).get("chapters") or [],
        "recommendations": (a.get("relevance") or {}).get("recommendations") or [],
        "stat_methods": (a.get("statistics") or {}).get("method_tags") or [],
        "flags": a.get("flags") or {},
        "timepoints": {k: tp.get(k) for k in ("covers_24h", "covers_48h", "covers_72h", "md_offsets")},
        "gps_variables": sorted({canon(v.get("name", ""), GPS_CANON)[1] for v in vars_
                                 if v.get("category") == "gps_external_load"}),
        "cmj_variables": sorted({canon(v.get("name", ""), CMJ_CANON)[1] for v in vars_
                                 if v.get("category") == "cmj_neuromuscular"}),
        "verification": a.get("verification"),
    }


def search(q: str, limit: int = 200) -> dict[str, Any]:
    """Volltextsuche über Analysen/Metadaten und PDF-Text (FTS5)."""
    tokens = [t for t in re.findall(r"[\w\-:+/]+", q or "", flags=re.UNICODE) if len(t) > 1]
    if not tokens:
        return {"query": q, "studies": {}}
    fts_q = " AND ".join('"' + t.replace('"', "") + '"*' for t in tokens)
    conn = db.get_conn()
    res: dict[int, dict[str, Any]] = {}
    try:
        for r in conn.execute(
                "SELECT study_id, snippet(studies_fts, 0, '«', '»', ' … ', 14) AS snip, bm25(studies_fts) AS rank "
                "FROM studies_fts WHERE studies_fts MATCH ? ORDER BY rank LIMIT ?", (fts_q, limit)):
            res.setdefault(r["study_id"], {"analysis_hit": r["snip"], "page_hits": []})
        for r in conn.execute(
                "SELECT study_id, page_number, snippet(pages_fts, 0, '«', '»', ' … ', 14) AS snip, "
                "bm25(pages_fts) AS rank FROM pages_fts WHERE pages_fts MATCH ? ORDER BY rank LIMIT ?",
                (fts_q, limit * 3)):
            e = res.setdefault(r["study_id"], {"analysis_hit": None, "page_hits": []})
            if len(e["page_hits"]) < 5:
                e["page_hits"].append({"page": r["page_number"], "snippet": r["snip"]})
    except Exception as exc:  # noqa: BLE001
        log.warning("FTS-Fehler: %s", exc)
    return {"query": q, "studies": res}


def search_in_study(study_id: int, q: str) -> list[dict[str, Any]]:
    q = (q or "").strip()
    if not q:
        return []
    out = []
    ql = q.lower()
    for p in get_pages(study_id):
        text = p["text"]
        tl = text.lower()
        idx = tl.find(ql)
        count = tl.count(ql)
        if idx >= 0:
            s = max(0, idx - 80)
            snippet = re.sub(r"\s+", " ", text[s: idx + len(q) + 80])
            out.append({"page": p["page_number"], "page_label": p["page_label"], "count": count,
                        "snippet": snippet})
    return out


# ---------------------------------------------------------------------------
# Kennzahlen & Lückenanalyse (deterministisch, nur aus importierten Studien)
# ---------------------------------------------------------------------------

def dashboard_stats() -> dict[str, Any]:
    studies = list_studies()
    analyzed = [s for s in studies if s["status"] == "analyzed"]
    by_year = Counter(s["year"] for s in analyzed if s["year"])
    by_design = Counter(DESIGN_CATEGORIES.get(s["design_category"] or "not_reported", "Sonstiges") for s in analyzed)
    topics = Counter(t for s in analyzed for t in s["topics"])
    var_counter = Counter(v for s in analyzed for v in s["gps_variables"] + s["cmj_variables"])
    rel_bins = Counter()
    for s in analyzed:
        if s["relevance_score"] is not None:
            b = min(int(s["relevance_score"] // 10) * 10, 90)
            rel_bins[b] += 1
    status = Counter(s["status"] for s in studies)
    return {
        "total": len(studies),
        "analyzed": len(analyzed),
        "high_relevance": sum(1 for s in analyzed if (s["relevance_score"] or 0) >= 70),
        "with_cmj": sum(1 for s in analyzed if s["uses_cmj"]),
        "with_gps": sum(1 for s in analyzed if s["uses_gps"]),
        "needs_ocr": status.get("needs_ocr", 0),
        "errors": status.get("error", 0),
        "pending": sum(status.get(k, 0) for k in ("extracted", "queued", "analyzing", "no_api")),
        "status": dict(status),
        "by_year": dict(sorted(by_year.items())),
        "by_design": dict(by_design.most_common()),
        "topics": dict(topics.most_common()),
        "variables": dict(var_counter.most_common(20)),
        "relevance_bins": {f"{b}–{b + 9 if b < 90 else 100}": rel_bins.get(b, 0) for b in range(0, 100, 10)},
        "chapters": {c["title"]: sum(1 for s in analyzed if c["key"] in s["chapters"]) for c in CHAPTERS},
    }


def _analyses() -> list[tuple[dict[str, Any], dict[str, Any]]]:
    rows = db.get_conn().execute(
        "SELECT id, title, authors, year, filename, relevance_score, analysis_json, user_tags, chapter_override "
        "FROM studies WHERE status='analyzed' AND analysis_json IS NOT NULL").fetchall()
    return [(db.row_to_dict(r), db.loads(r["analysis_json"], {})) for r in rows]


def short_ref(row: dict[str, Any]) -> str:
    authors = (row.get("authors") or "").strip()
    first = re.split(r"[,;&]| and | und ", authors)[0].strip() if authors else ""
    surname = first.split()[-1] if first else (row.get("filename") or "Studie")
    many = authors.count(",") >= 1 or " and " in authors or "&" in authors or ";" in authors
    return f"{surname}{' et al.' if many else ''} ({row.get('year') or 'o. J.'})"


def gap_counts() -> dict[str, Any]:
    data = _analyses()
    gps = defaultdict(list)
    cmj = defaultdict(list)
    tp = {"24h": [], "48h": [], "72h": []}
    md = Counter()
    pro_football = []
    designs = Counter()
    stats = Counter()
    levels = Counter()
    combos = {"gps_and_cmj": [], "gps_only": [], "cmj_only": []}
    limitations = []
    for row, a in data:
        ref = {"id": row["id"], "ref": short_ref(row), "title": row["title"]}
        seen_g, seen_c = set(), set()
        for v in a.get("variables") or []:
            if v.get("category") == "gps_external_load":
                k = canon(v.get("name", ""), GPS_CANON)[1]
                if k not in seen_g:
                    gps[k].append(ref)
                    seen_g.add(k)
            elif v.get("category") == "cmj_neuromuscular":
                k = canon(v.get("name", ""), CMJ_CANON)[1]
                if k not in seen_c:
                    cmj[k].append(ref)
                    seen_c.add(k)
        t = a.get("timepoints") or {}
        for h in ("24h", "48h", "72h"):
            if t.get(f"covers_{h}"):
                tp[h].append(ref)
        for m in t.get("md_offsets") or []:
            md[m.upper().replace(" ", "")] += 1
        f = a.get("flags") or {}
        if f.get("professional_football"):
            pro_football.append(ref)
        if f.get("uses_gps") and f.get("uses_cmj"):
            combos["gps_and_cmj"].append(ref)
        elif f.get("uses_gps"):
            combos["gps_only"].append(ref)
        elif f.get("uses_cmj"):
            combos["cmj_only"].append(ref)
        designs[DESIGN_CATEGORIES.get((a.get("design") or {}).get("design_category", "not_reported"), "Sonstiges")] += 1
        levels[LEVEL_CATEGORIES.get((a.get("sample") or {}).get("level_category", "not_reported"), "Sonstiges")] += 1
        for s in (a.get("statistics") or {}).get("method_tags") or []:
            stats[STAT_METHODS.get(s, s)] += 1
        for lim in (a.get("critical") or {}).get("limitations_reported") or []:
            if lim.get("status") != "not_reported":
                limitations.append({**ref, "text": lim.get("value"), "page": lim.get("page"),
                                    "page_label": lim.get("page_label")})
    def _sorted(d):
        return [{"name": k, "count": len(v), "studies": v} for k, v in sorted(d.items(), key=lambda x: -len(x[1]))]
    return {
        "n_analyzed": len(data),
        "gps_variables": _sorted(gps),
        "cmj_variables": _sorted(cmj),
        "all_cmj_params": [label for _, label, _ in CMJ_CANON],
        "all_gps_params": [label for _, label, _ in GPS_CANON],
        "timepoints": {k: {"count": len(v), "studies": v} for k, v in tp.items()},
        "md_offsets": dict(md.most_common()),
        "professional_football": {"count": len(pro_football), "studies": pro_football},
        "combos": {k: {"count": len(v), "studies": v} for k, v in combos.items()},
        "designs": dict(designs.most_common()),
        "levels": dict(levels.most_common()),
        "stat_methods": dict(stats.most_common()),
        "limitations": limitations,
    }


def digest(row: dict[str, Any], a: dict[str, Any], detail: str = "full") -> dict[str, Any]:
    """Kompakte, belegte Darstellung einer Analyse als Eingabe für Synthesen."""
    def c(node):
        if not isinstance(node, dict):
            return None
        if node.get("status") == "not_reported":
            return "Nicht berichtet"
        return {"v": node.get("value"), "p": node.get("page") or 0, "s": node.get("status")}

    def cl(nodes, n=8):
        return [c(x) for x in (nodes or [])[:n] if x.get("status") != "not_reported"]

    d = a.get("design") or {}
    s = a.get("sample") or {}
    m = a.get("methods") or {}
    r = a.get("results") or {}
    cr = a.get("critical") or {}
    out = {
        "study_id": row["id"],
        "ref": short_ref(row),
        "title": row.get("title"),
        "design_category": d.get("design_category"),
        "research_question": c(d.get("research_question")),
        "study_type": c(d.get("study_type")),
        "sample": {"n": c(s.get("n_participants")), "level": s.get("level_category"),
                   "sport": s.get("sport_normalized"), "age": c(s.get("age")), "sex": c(s.get("sex"))},
        "gps_system": c(m.get("gps_system")),
        "cmj_device": c(m.get("cmj_device")),
        "timing": c(m.get("measurement_timing")),
        "timepoints": a.get("timepoints", {}).get("md_offsets"),
        "statistics": c(m.get("statistical_methods")),
        "repeated_measures": c(m.get("repeated_measures_handling")),
        "variables": [{"name": v.get("name"), "cat": v.get("category"), "def": v.get("definition"),
                       "p": v.get("page") or 0} for v in (a.get("variables") or [])[:30]],
        "key_findings": cl(r.get("key_findings")),
        "fatigue_recovery": cl(r.get("fatigue_recovery_statements")),
        "effect_sizes": cl(r.get("effect_sizes"), 6),
        "limitations": cl(cr.get("limitations_reported"), 6),
        "relevance": row.get("relevance_score"),
    }
    if detail == "full":
        out.update({
            "confounders": c(m.get("confounders")),
            "load_definitions": c(m.get("load_variable_definitions")),
            "correlations": cl(r.get("correlations"), 6),
            "timepoint_differences": cl(r.get("timepoint_differences"), 6),
            "weaknesses_ai": cl(cr.get("weaknesses"), 5),
        })
    return out


def validate_citations(output: dict[str, Any], allowed: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """Prüft KI-Zitationen in Synthesen: Studie im Input? Seite existiert? Seite durch Analyse belegt?"""
    conn = db.get_conn()
    page_counts = {r["id"]: r["page_count"] for r in conn.execute("SELECT id, page_count FROM studies")}
    ev_pages: dict[int, set[int]] = defaultdict(set)
    for r in conn.execute("SELECT study_id, page FROM evidence WHERE page IS NOT NULL"):
        ev_pages[r["study_id"]].add(r["page"])
    labels = {(r["study_id"], r["page_number"]): r["page_label"]
              for r in conn.execute("SELECT study_id, page_number, page_label FROM pages WHERE page_label IS NOT NULL")}
    problems = 0

    def walk(node):
        nonlocal problems
        if isinstance(node, dict):
            if "citations" in node and isinstance(node["citations"], list):
                for cit in node["citations"]:
                    sid, pg = cit.get("study_id"), cit.get("page") or 0
                    if sid not in allowed:
                        cit["check"] = "invalid_study"
                        problems += 1
                    elif pg and pg > page_counts.get(sid, 0):
                        cit["check"] = "invalid_page"
                        problems += 1
                    elif pg and pg in ev_pages.get(sid, set()):
                        cit["check"] = "matches_evidence"
                    elif pg:
                        cit["check"] = "page_exists"
                    else:
                        cit["check"] = "no_page"
                    cit["ref"] = short_ref(allowed[sid]) if sid in allowed else f"Unbekannte Studie {sid}"
                    cit["page_label"] = labels.get((sid, pg))
                if not node["citations"] and node.get("kind") == "literature_finding":
                    node["unsupported"] = True
                    problems += 1
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(output)
    output["_citation_problems"] = problems
    return output


def save_ai_output(kind: str, key: str, study_ids: list[int], output: dict[str, Any], model: str | None) -> dict[str, Any]:
    with db.tx() as c:
        cur = c.execute("INSERT INTO ai_outputs(kind, key, study_ids, output_json, model, created_at) "
                        "VALUES(?,?,?,?,?,?)", (kind, key, db.dumps(study_ids), db.dumps(output), model, db.now_iso()))
        oid = cur.lastrowid
    return get_ai_output(oid)


def get_ai_output(oid: int) -> dict[str, Any] | None:
    r = db.get_conn().execute("SELECT * FROM ai_outputs WHERE id=?", (oid,)).fetchone()
    if not r:
        return None
    d = db.row_to_dict(r)
    d["study_ids"] = db.loads(d["study_ids"], [])
    d["output"] = db.loads(d.pop("output_json"), {})
    return d


def latest_ai_output(kind: str, key: str) -> dict[str, Any] | None:
    r = db.get_conn().execute("SELECT id FROM ai_outputs WHERE kind=? AND key=? ORDER BY id DESC LIMIT 1",
                              (kind, key)).fetchone()
    return get_ai_output(r["id"]) if r else None


def studies_for_chapter(key: str) -> list[dict[str, Any]]:
    out = []
    for s in list_studies():
        if s["status"] == "analyzed" and key in (s["chapters"] or []):
            out.append(s)
    out.sort(key=lambda s: (-(s["relevance_score"] or 0)))
    return out


def evidence_for_study_ids(ids: list[int]) -> list[dict[str, Any]]:
    if not ids:
        return []
    q = ",".join("?" * len(ids))
    return [db.row_to_dict(r) for r in db.get_conn().execute(
        f"SELECT * FROM evidence WHERE study_id IN ({q}) ORDER BY study_id, id", ids)]
