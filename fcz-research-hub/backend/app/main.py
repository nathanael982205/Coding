"""FastAPI-Anwendung: REST-API + Auslieferung des Frontends unter http://localhost:8000."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import Body, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import assistants, config, db, demo, exports, jobs, llm, services
from .schema import CHAPTER_KEYS, vocab

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("research_hub")

app = FastAPI(title="FCZ Thesis Research Hub", version="1.0.0")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    jobs.recover_interrupted()
    log.info("Datenverzeichnis: %s | KI konfiguriert: %s | Modell: %s",
             config.DATA_DIR, config.ai_configured(), config.active_model())


def _study_or_404(study_id: int) -> dict[str, Any]:
    row = services.get_study_row(study_id)
    if not row:
        raise HTTPException(404, "Studie nicht gefunden.")
    return row


def _ai_guard() -> None:
    if not config.ai_configured():
        raise HTTPException(503, f"KI nicht konfiguriert: {config.key_variable()} in .env eintragen und Server neu starten.")


def _ai_call(fn, *args):
    _ai_guard()
    try:
        return fn(*args)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except (llm.AIError, llm.AIUnavailable) as exc:
        raise HTTPException(502, str(exc)) from exc


# ---------------------------------------------------------------- Status / Einstellungen

@app.get("/api/status")
def status() -> dict[str, Any]:
    conn = db.get_conn()
    n = conn.execute("SELECT count(*) FROM studies").fetchone()[0]
    return {
        "ai_configured": config.ai_configured(),
        "provider": config.PROVIDER,
        "provider_label": "OpenAI (ChatGPT)" if config.PROVIDER == "openai" else "Anthropic (Claude)",
        "key_variable": config.key_variable(),
        "model": config.active_model(),
        "effort": config.active_effort(),
        "refusal_fallback": config.CLAUDE_REFUSAL_FALLBACK and config.PROVIDER == "anthropic",
        "study_count": n,
        "active_jobs": jobs.active(),
        "data_dir": str(config.DATA_DIR),
        "max_text_chars": config.MAX_TEXT_CHARS,
    }


@app.post("/api/test-ai")
def test_ai() -> dict[str, Any]:
    return _ai_call(llm.test_connection)


@app.get("/api/vocab")
def get_vocab() -> dict[str, Any]:
    v = vocab()
    v["method_topics"] = [{"key": t["key"], "title": t["title"]} for t in assistants.METHOD_TOPICS]
    return v


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    return {"thesis_context": db.get_setting("thesis_context") or llm.DEFAULT_THESIS_CONTEXT,
            "thesis_context_is_default": db.get_setting("thesis_context") is None}


@app.put("/api/settings")
def put_settings(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    ctx = (payload.get("thesis_context") or "").strip()
    db.set_setting("thesis_context", ctx or None)
    return get_settings()


@app.get("/api/demo")
def get_demo() -> dict[str, Any]:
    return demo.demo_payload()


# ---------------------------------------------------------------- Studien

@app.get("/api/studies")
def list_studies() -> list[dict[str, Any]]:
    return services.list_studies()


@app.post("/api/studies/upload")
async def upload(files: list[UploadFile] = File(...), analyze: bool = Query(True)) -> dict[str, Any]:
    results = []
    for f in files:
        content = await f.read()
        if len(content) > config.MAX_UPLOAD_MB * 1024 * 1024:
            results.append({"filename": f.filename, "result": "error",
                            "message": f"Datei größer als {config.MAX_UPLOAD_MB} MB."})
            continue
        try:
            res = services.import_pdf(f.filename or "dokument.pdf", content)
        except Exception as exc:  # noqa: BLE001
            log.exception("Import fehlgeschlagen: %s", f.filename)
            res = {"filename": f.filename, "result": "error", "message": f"Import fehlgeschlagen: {exc}"}
        if res.get("result") == "imported" and res.get("status") == "extracted":
            if analyze and config.ai_configured():
                jobs.enqueue(res["study_id"])
                res["status"] = "queued"
            elif not config.ai_configured():
                with db.tx() as c:
                    c.execute("UPDATE studies SET status='no_api', status_message=? WHERE id=?",
                              ("Text extrahiert. KI-Analyse ausstehend (kein API-Schlüssel konfiguriert).",
                               res["study_id"]))
                res["status"] = "no_api"
        results.append(res)
    return {"results": results, "ai_configured": config.ai_configured()}


@app.get("/api/studies/{study_id}")
def get_study(study_id: int) -> dict[str, Any]:
    row = _study_or_404(study_id)
    pages = services.get_pages(study_id)
    row["analysis"] = db.loads(row.pop("analysis_json"), None)
    for k, d in (("text_quality", {}), ("pdf_metadata", {}), ("heuristics", {}), ("user_tags", []),
                 ("chapter_override", None), ("analysis_usage", None)):
        row[k] = db.loads(row.get(k), d)
    row["pages"] = [{k: p[k] for k in ("page_number", "page_label", "label_source", "char_count", "quality")}
                    for p in pages]
    row["ref"] = services.short_ref(row)
    row.pop("sha256", None)
    return row


@app.get("/api/studies/{study_id}/pdf")
def get_pdf(study_id: int) -> FileResponse:
    row = _study_or_404(study_id)
    path = config.PDF_DIR / row["stored_name"]
    if not path.exists():
        raise HTTPException(404, "PDF-Datei fehlt im Datenordner.")
    return FileResponse(path, media_type="application/pdf", filename=row["filename"],
                        content_disposition_type="inline")


@app.get("/api/studies/{study_id}/pages/{page}/text")
def page_text(study_id: int, page: int) -> dict[str, Any]:
    _study_or_404(study_id)
    r = db.get_conn().execute("SELECT * FROM pages WHERE study_id=? AND page_number=?", (study_id, page)).fetchone()
    if not r:
        raise HTTPException(404, "Seite nicht gefunden.")
    return db.row_to_dict(r)


@app.get("/api/studies/{study_id}/search")
def search_study(study_id: int, q: str = "") -> list[dict[str, Any]]:
    _study_or_404(study_id)
    return services.search_in_study(study_id, q)


@app.get("/api/studies/{study_id}/highlight")
def highlight(study_id: int, page: int, q: str = "") -> dict[str, Any]:
    row = _study_or_404(study_id)
    from .pdf_processing import find_highlights
    return find_highlights(config.PDF_DIR / row["stored_name"], page, q)


@app.post("/api/studies/{study_id}/analyze")
def analyze(study_id: int) -> dict[str, Any]:
    row = _study_or_404(study_id)
    _ai_guard()
    if row["status"] == "needs_ocr":
        raise HTTPException(400, "PDF benötigt OCR – ohne auslesbaren Text ist keine verlässliche Analyse möglich.")
    started = jobs.enqueue(study_id)
    return {"queued": started}


@app.post("/api/studies/analyze-pending")
def analyze_pending(include_analyzed: bool = False) -> dict[str, Any]:
    _ai_guard()
    statuses = ["extracted", "no_api", "error"] + (["analyzed"] if include_analyzed else [])
    q = ",".join("?" * len(statuses))
    ids = [r["id"] for r in db.get_conn().execute(f"SELECT id FROM studies WHERE status IN ({q})", statuses)]
    queued = [i for i in ids if jobs.enqueue(i)]
    return {"queued": queued}


@app.patch("/api/studies/{study_id}")
def patch_study(study_id: int, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    _study_or_404(study_id)
    allowed_tags = set(vocab()["user_tags"])
    with db.tx() as c:
        if "notes" in payload:
            c.execute("UPDATE studies SET notes=? WHERE id=?", (str(payload["notes"] or ""), study_id))
        if "user_tags" in payload:
            tags = [t for t in payload["user_tags"] or [] if t in allowed_tags]
            c.execute("UPDATE studies SET user_tags=? WHERE id=?", (db.dumps(tags), study_id))
        if "chapter_override" in payload:
            ch = payload["chapter_override"]
            val = None if ch is None else db.dumps([k for k in ch if k in CHAPTER_KEYS])
            c.execute("UPDATE studies SET chapter_override=? WHERE id=?", (val, study_id))
    if "notes" in payload:
        services._refresh_study_fts(study_id)
    return get_study(study_id)


@app.delete("/api/studies/{study_id}")
def delete_study(study_id: int) -> dict[str, Any]:
    if not services.delete_study(study_id):
        raise HTTPException(404, "Studie nicht gefunden.")
    return {"deleted": study_id}


@app.get("/api/studies/{study_id}/evidence")
def study_evidence(study_id: int) -> list[dict[str, Any]]:
    _study_or_404(study_id)
    return services.evidence_for_study_ids([study_id])


# ---------------------------------------------------------------- Suche / Dashboard

@app.get("/api/search")
def search(q: str = "") -> dict[str, Any]:
    return services.search(q)


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    return services.dashboard_stats()


@app.get("/api/matrix")
def matrix() -> dict[str, Any]:
    return {"columns": [{"key": k, "label": l} for k, l in exports.MATRIX_COLUMNS], "rows": exports.matrix_rows()}


# ---------------------------------------------------------------- Vergleich

@app.post("/api/compare")
def compare(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    ids = [int(i) for i in payload.get("ids", [])][:5]
    if len(ids) < 2:
        raise HTTPException(400, "Bitte 2–5 Studien auswählen.")
    table = assistants.compare_table(ids)
    table["latest_ai"] = services.latest_ai_output("compare", "-".join(str(i) for i in sorted(ids)))
    return table


@app.post("/api/compare/ai")
def compare_ai(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    ids = [int(i) for i in payload.get("ids", [])][:5]
    return _ai_call(assistants.run_compare_ai, ids)


# ---------------------------------------------------------------- Theorie / Methodik / Lücken

@app.get("/api/theory/{key}")
def theory(key: str) -> dict[str, Any]:
    if key not in CHAPTER_KEYS:
        raise HTTPException(404, "Unbekanntes Kapitel.")
    return assistants.chapter_overview(key)


@app.post("/api/theory/{key}/ai")
def theory_ai(key: str) -> dict[str, Any]:
    if key not in CHAPTER_KEYS:
        raise HTTPException(404, "Unbekanntes Kapitel.")
    return _ai_call(assistants.run_chapter_ai, key)


@app.get("/api/methods/{key}")
def methods(key: str) -> dict[str, Any]:
    if key not in assistants.METHOD_TOPIC_KEYS:
        raise HTTPException(404, "Unbekanntes Thema.")
    return assistants.method_topic_evidence(key)


@app.post("/api/methods/{key}/ai")
def methods_ai(key: str) -> dict[str, Any]:
    if key not in assistants.METHOD_TOPIC_KEYS:
        raise HTTPException(404, "Unbekanntes Thema.")
    return _ai_call(assistants.run_method_ai, key)


@app.get("/api/gaps")
def gaps() -> dict[str, Any]:
    d = services.gap_counts()
    d["latest_ai"] = services.latest_ai_output("gaps", "all")
    return d


@app.post("/api/gaps/ai")
def gaps_ai() -> dict[str, Any]:
    return _ai_call(assistants.run_gaps_ai)


@app.put("/api/notes/{scope}/{key}")
def put_note(scope: str, key: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    if scope not in {"chapter", "method"}:
        raise HTTPException(400, "Ungültiger Bereich.")
    return assistants.save_note(scope, key, str(payload.get("content", "")))


# ---------------------------------------------------------------- Export / Backup

EXPORTS = {
    "csv": ("text/csv; charset=utf-8", "literaturmatrix.csv", exports.to_csv),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "literaturmatrix.xlsx",
             exports.to_xlsx),
    "json": ("application/json", "analysen.json", exports.to_json),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "kapitelnotizen.docx",
             exports.to_docx),
    "bibtex": ("application/x-bibtex; charset=utf-8", "literatur.bib", exports.to_bibtex),
    "ris": ("application/x-research-info-systems; charset=utf-8", "literatur.ris", exports.to_ris),
}


@app.get("/api/export/{fmt}")
def export(fmt: str) -> Response:
    if fmt not in EXPORTS:
        raise HTTPException(404, "Unbekanntes Exportformat.")
    media, name, fn = EXPORTS[fmt]
    return Response(fn(), media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.post("/api/backup")
def backup() -> FileResponse:
    path = exports.create_backup()
    return FileResponse(path, media_type="application/zip", filename=path.name)


@app.get("/api/backups")
def list_backups() -> list[dict[str, Any]]:
    return [{"name": p.name, "size": p.stat().st_size}
            for p in sorted(config.BACKUP_DIR.glob("*.zip"), reverse=True)]


@app.post("/api/restore")
async def restore(file: UploadFile = File(...)) -> dict[str, Any]:
    if jobs.active():
        raise HTTPException(409, "Während laufender Analysen ist keine Wiederherstellung möglich.")
    try:
        return exports.restore_backup(await file.read())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


# ---------------------------------------------------------------- Frontend

app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="frontend")
