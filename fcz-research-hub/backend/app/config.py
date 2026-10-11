"""Zentrale Konfiguration. Liest Werte aus .env (nur im Backend)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=True)


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "ja", "on"}


DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data")).resolve()
PDF_DIR = DATA_DIR / "pdfs"
BACKUP_DIR = DATA_DIR / "backups"
DB_PATH = DATA_DIR / "research_hub.sqlite3"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# KI-Anbieter: "anthropic" (Claude) oder "openai" (ChatGPT/GPT-Modelle)
PROVIDER = os.getenv("HUB_PROVIDER", "anthropic").strip().lower()
if PROVIDER not in {"anthropic", "openai"}:
    PROVIDER = "anthropic"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("HUB_OPENAI_MODEL", "gpt-5.5").strip()
OPENAI_EFFORT = os.getenv("HUB_OPENAI_EFFORT", "medium").strip()
# Max. Antwortlänge pro OpenAI-Anfrage (zählt bei OpenAI gegen das Token-pro-Minute-Limit)
OPENAI_MAX_OUTPUT = int(os.getenv("HUB_OPENAI_MAX_OUTPUT", "32000"))
CLAUDE_MODEL = os.getenv("HUB_CLAUDE_MODEL", "claude-opus-5-5").strip()
CLAUDE_EFFORT = os.getenv("HUB_CLAUDE_EFFORT", "high").strip()
# Server-seitiger Refusal-Fallback (Claude API). Bei Problemen in .env abschalten.
CLAUDE_REFUSAL_FALLBACK = _bool("HUB_REFUSAL_FALLBACK", True)
ANALYSIS_WORKERS = int(os.getenv("ANALYSIS_WORKERS", "2"))
# Obergrenze für an Claude gesendeten Text pro Studie (Zeichen). Wird sie
# überschritten, wird dies in der Analyse ausdrücklich vermerkt.
MAX_TEXT_CHARS = int(os.getenv("MAX_TEXT_CHARS", "600000"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "80"))

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

for d in (DATA_DIR, PDF_DIR, BACKUP_DIR):
    d.mkdir(parents=True, exist_ok=True)


def ai_configured() -> bool:
    return bool(OPENAI_API_KEY) if PROVIDER == "openai" else bool(ANTHROPIC_API_KEY)


def active_model() -> str:
    return OPENAI_MODEL if PROVIDER == "openai" else CLAUDE_MODEL


def active_effort() -> str:
    return OPENAI_EFFORT if PROVIDER == "openai" else CLAUDE_EFFORT


def key_variable() -> str:
    return "OPENAI_API_KEY" if PROVIDER == "openai" else "ANTHROPIC_API_KEY"
