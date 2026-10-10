"""SQLite-Datenhaltung (Schema, Verbindungen, FTS5-Volltextindex)."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from . import config

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS studies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filename        TEXT NOT NULL,              -- Originaldateiname
    stored_name     TEXT NOT NULL UNIQUE,       -- Dateiname im Ablageordner
    sha256          TEXT NOT NULL UNIQUE,       -- Dublettenerkennung (Inhalt)
    file_size       INTEGER NOT NULL,
    page_count      INTEGER NOT NULL DEFAULT 0,
    imported_at     TEXT NOT NULL,
    -- Verarbeitungsstatus: extracted | queued | analyzing | analyzed | error | needs_ocr | no_api
    status          TEXT NOT NULL DEFAULT 'extracted',
    status_message  TEXT,
    text_quality    TEXT,                       -- JSON: Seitenstatistik / OCR-Hinweise
    pdf_metadata    TEXT,                       -- JSON: eingebettete PDF-Metadaten
    heuristics      TEXT,                       -- JSON: regelbasiert erkannte Angaben (ohne KI)
    -- Flache Felder für Filter/Sortierung (aus Analyse abgeleitet)
    title           TEXT,
    authors         TEXT,
    year            INTEGER,
    journal         TEXT,
    doi             TEXT,
    design_category TEXT,
    sample_n        INTEGER,
    level_category  TEXT,
    sport           TEXT,
    uses_gps        INTEGER,
    uses_cmj        INTEGER,
    relevance_score REAL,
    short_summary   TEXT,
    analysis_json   TEXT,                       -- vollständige strukturierte Analyse
    analysis_model  TEXT,
    analyzed_at     TEXT,
    analysis_usage  TEXT,                       -- JSON: Token-Verbrauch
    -- Persönliche Daten
    notes           TEXT NOT NULL DEFAULT '',
    user_tags       TEXT NOT NULL DEFAULT '[]', -- JSON-Liste
    chapter_override TEXT                       -- JSON-Liste oder NULL
);

CREATE TABLE IF NOT EXISTS pages (
    study_id     INTEGER NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    page_number  INTEGER NOT NULL,              -- physische PDF-Seite (1-basiert)
    page_label   TEXT,                          -- gedruckte Seitenzahl (Label oder Heuristik)
    label_source TEXT,                          -- 'pdf_label' | 'heuristic' | NULL
    text         TEXT NOT NULL DEFAULT '',
    char_count   INTEGER NOT NULL DEFAULT 0,
    quality      TEXT NOT NULL,                 -- ok | low_text | scanned | empty
    PRIMARY KEY (study_id, page_number)
);

CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
    text, study_id UNINDEXED, page_number UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE VIRTUAL TABLE IF NOT EXISTS studies_fts USING fts5(
    content, study_id UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS evidence (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    study_id     INTEGER NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    field_path   TEXT NOT NULL,
    statement    TEXT NOT NULL,
    page         INTEGER,                      -- physische PDF-Seite
    page_label   TEXT,                         -- gedruckte Seitenzahl
    quote        TEXT,
    status       TEXT NOT NULL,                -- verified | uncertain | not_reported
    source_type  TEXT NOT NULL,                -- author_statement | ai_summary | ai_assessment
    quote_check  TEXT                          -- exact | fuzzy | not_found | no_quote
);
CREATE INDEX IF NOT EXISTS idx_evidence_study ON evidence(study_id);

CREATE TABLE IF NOT EXISTS ai_outputs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL,                 -- compare | theory | methods | gaps
    key         TEXT NOT NULL,                 -- z. B. Kapitel- oder Themen-Schlüssel
    study_ids   TEXT NOT NULL,                 -- JSON-Liste der verwendeten Studien
    output_json TEXT NOT NULL,
    model       TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_outputs_kind ON ai_outputs(kind, key);

CREATE TABLE IF NOT EXISTS user_notes (
    scope      TEXT NOT NULL,                  -- chapter | method
    key        TEXT NOT NULL,
    content    TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (scope, key)
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_local = threading.local()
_write_lock = threading.RLock()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _connect()
        _local.conn = conn
    return conn


def close_thread_conn() -> None:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    """Schreibtransaktion (serialisiert über einen Prozess-Lock)."""
    conn = get_conn()
    with _write_lock:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def init_db() -> None:
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def loads(value: str | None, default: Any = None) -> Any:
    if value is None or value == "":
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def get_setting(key: str, default: Any = None) -> Any:
    row = get_conn().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return loads(row["value"], default) if row else default


def set_setting(key: str, value: Any) -> None:
    with tx() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, dumps(value)),
        )
