"""Claude-API-Anbindung (ausschließlich im Backend; der API-Schlüssel verlässt nie den Server).

Es werden nur Texte der vom Nutzer importierten wissenschaftlichen PDFs bzw.
daraus abgeleitete Analysen übertragen – keine Spieler- oder Vereinsdaten."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import anthropic

from . import config
from .schema import (ANALYSIS_SCHEMA, CHAPTERS, DESIGN_CATEGORIES, RECOMMENDATIONS,
                     RELEVANCE_LABELS, RELEVANCE_WEIGHTS, TOPICS)

log = logging.getLogger("research_hub.llm")

DEFAULT_THESIS_CONTEXT = (
    "Masterarbeit (Sportwissenschaft) in Kooperation mit dem FC Zürich: Zusammenhang zwischen "
    "GPS-basierter externer Belastung (Total Distance, High-Speed Running, Sprint Distance, "
    "Accelerations, Decelerations; Match- und Trainingsbelastung) und der neuromuskulären Readiness "
    "professioneller Fußballspieler, gemessen über die Countermovement-Jump-Leistung (CMJ; Sprunghöhe "
    "und Force-Time-Parameter) 24–72 Stunden nach Spiel- oder Trainingsbelastung (MD+1, MD+2, MD+3). "
    "Relevante Aspekte: individuelle Baselines, interindividuelle Unterschiede, Wellness/RPE/Internal "
    "Load, Reliabilität/Validität der Monitoringinstrumente, Statistik für wiederholte Messungen "
    "(z. B. Mixed-Effects-Modelle). Mögliche Datenquellen: WIMU-GPS und VALD ForceDecks."
)


class AIUnavailable(RuntimeError):
    pass


class AIError(RuntimeError):
    pass


def _client() -> anthropic.Anthropic:
    if not config.ai_configured():
        raise AIUnavailable("Kein ANTHROPIC_API_KEY in .env konfiguriert – KI-Funktionen sind deaktiviert.")
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=3, timeout=900)


def _extract_json(text: str) -> Any:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=0)
    return json.loads(text[start:])


def call_json(system: str, user_content: str, schema: dict[str, Any],
              max_tokens: int = 64000) -> tuple[Any, dict[str, Any]]:
    """Strukturierter Aufruf mit JSON-Schema. Gibt (daten, meta) zurück."""
    client = _client()
    use_schema = True
    use_fallback = config.CLAUDE_REFUSAL_FALLBACK
    last_exc: Exception | None = None
    for _attempt in range(3):
        output_config: dict[str, Any] = {"effort": config.CLAUDE_EFFORT}
        sys_text = system
        if use_schema:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        else:
            sys_text = (system + "\n\nAntworte ausschließlich mit einem JSON-Objekt, das exakt diesem "
                        "JSON-Schema entspricht (keine Erklärungen, kein Markdown):\n" + json.dumps(schema))
        kwargs: dict[str, Any] = {
            "model": config.CLAUDE_MODEL,
            "max_tokens": max_tokens,
            "system": sys_text,
            "messages": [{"role": "user", "content": user_content}],
            "output_config": output_config,
        }
        try:
            if use_fallback:
                with client.beta.messages.stream(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
                ) as stream:
                    msg = stream.get_final_message()
            else:
                with client.messages.stream(**kwargs) as stream:
                    msg = stream.get_final_message()
        except anthropic.AuthenticationError as exc:
            raise AIError("API-Schlüssel ungültig (401). Bitte ANTHROPIC_API_KEY in .env prüfen.") from exc
        except anthropic.PermissionDeniedError as exc:
            raise AIError(f"Zugriff verweigert (403): {exc.message}") from exc
        except anthropic.NotFoundError as exc:
            raise AIError(f"Modell '{config.CLAUDE_MODEL}' nicht gefunden (404). HUB_CLAUDE_MODEL prüfen.") from exc
        except anthropic.BadRequestError as exc:
            last_exc = exc
            msg_l = str(exc.message).lower()
            if use_fallback and ("fallback" in msg_l or "beta" in msg_l):
                log.warning("Fallback-Parameter abgelehnt, erneuter Versuch ohne: %s", exc.message)
                use_fallback = False
                continue
            if use_schema and ("schema" in msg_l or "format" in msg_l or "output_config" in msg_l):
                log.warning("JSON-Schema abgelehnt, erneuter Versuch mit Schema im Prompt: %s", exc.message)
                use_schema = False
                continue
            raise AIError(f"Ungültige Anfrage (400): {exc.message}") from exc
        except anthropic.RateLimitError as exc:
            raise AIError("Rate-Limit erreicht (429). Bitte später erneut versuchen.") from exc
        except anthropic.APIStatusError as exc:
            raise AIError(f"API-Fehler {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise AIError("Keine Verbindung zur Claude API (Netzwerk/Proxy prüfen).") from exc

        if msg.stop_reason == "refusal":
            raise AIError("Die Anfrage wurde vom Modell abgelehnt (refusal).")
        if msg.stop_reason == "max_tokens":
            raise AIError("Antwort wurde wegen max_tokens abgeschnitten – Analyse unvollständig.")
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        try:
            data = _extract_json(text)
        except (ValueError, json.JSONDecodeError) as exc:
            last_exc = exc
            if use_schema:
                raise AIError("Antwort war kein gültiges JSON.") from exc
            continue
        usage = getattr(msg, "usage", None)
        meta = {
            "model": getattr(msg, "model", config.CLAUDE_MODEL),
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "structured_output": use_schema,
        }
        return data, meta
    raise AIError(f"KI-Aufruf fehlgeschlagen: {last_exc}")


# ---------------------------------------------------------------------------
# Studienanalyse
# ---------------------------------------------------------------------------

def _relevance_criteria() -> str:
    return "\n".join(f"- {RELEVANCE_LABELS[k]} ({int(w * 100)} %) -> Feld relevance.{k}"
                     for k, w in RELEVANCE_WEIGHTS.items())


ANALYSIS_SYSTEM = """Du bist ein sorgfältiger wissenschaftlicher Research Assistant (Sportwissenschaft, \
Fußball-Performance-Analytik, Belastungsmonitoring, neuromuskuläre Ermüdung). Du analysierst EINE \
wissenschaftliche Studie und füllst das vorgegebene JSON-Schema auf Deutsch aus.

Oberste Regeln (wissenschaftliche Nachvollziehbarkeit):
1. Erfinde niemals Informationen, Zahlen, Ergebnisse, Autoren oder Quellen. Verwende ausschließlich den \
gelieferten Dokumenttext.
2. Fehlt eine Information, setze value auf "Nicht berichtet" (oder "Nicht aus dem Dokument ersichtlich"), \
status "not_reported", page 0, quote "".
3. Jede Angabe aus dem Dokument (source_type "author_statement") braucht page = physische PDF-Seite gemäß \
den Markern [[PDF-SEITE n ...]] (NICHT die gedruckte Journal-Seitenzahl) und ein WÖRTLICHES Zitat \
(5–40 Wörter, exakt wie im Text, Originalsprache, keine Auslassungen/Umformulierungen) von genau dieser Seite. \
Zitate werden automatisch gegen den PDF-Text geprüft.
4. status: "verified" nur, wenn die Angabe direkt und eindeutig im zitierten Text steht; "uncertain", wenn \
sie abgeleitet, unklar, nur teilweise berichtet oder aus Tabellen/Abbildungen schwer lesbar ist.
5. source_type unterscheidet: "author_statement" = Aussage/Angabe der Autoren; "ai_summary" = deine \
zusammenfassende Formulierung mehrerer Stellen (wenn möglich trotzdem Seite+Zitat der wichtigsten Stelle); \
"ai_assessment" = deine methodische Bewertung (Stärken/Schwächen/Übertragbarkeit/Vergleichbarkeit; \
quote darf leer sein, page der Bezugsstelle wenn sinnvoll).
6. Zahlen (n, Alter, Effektgrößen, r, p, KI) exakt mit Einheit übernehmen. Keine Rundung.
7. Limitationen der Autoren (critical.limitations_reported, author_statement) streng von deinen eigenen \
methodischen Schwächen (critical.weaknesses, ai_assessment) trennen.
8. Variablen-Liste: alle erhobenen Variablen mit Kategorie, Definition/Schwellenwert, Einheit, Gerät, \
Seite und Zitat. Nichts ergänzen, was nicht berichtet wurde.
9. Wenn Text von Seiten fehlt (Scan/Abbildung) oder abgeschnitten wurde, weise in betroffenen Feldern \
darauf hin, statt zu raten.
10. Ergebnislisten dürfen leer sein, wenn nichts berichtet wurde. Keine Füllinhalte.

Relevanzbewertung für die Masterarbeit (interne Passung, KEINE Qualitätsbewertung der Studie). \
Vergib je Kriterium 0–100 mit kurzer, nachvollziehbarer Begründung:
{criteria}
Der Gesamtscore wird vom System gewichtet berechnet. Empfehlungen (recommendations) und passende \
Theoriekapitel (chapters) aus den erlaubten Werten wählen.

Kontext der Masterarbeit:
{thesis}

Theoriekapitel: {chapters}
"""


def build_document_text(pages: list[dict[str, Any]], max_chars: int) -> tuple[str, list[int]]:
    parts: list[str] = []
    used = 0
    omitted: list[int] = []
    for p in pages:
        label = f" | gedruckte Seite: {p['page_label']}" if p.get("page_label") else ""
        if p["quality"] in {"scanned", "empty", "garbled"}:
            parts.append(f"[[PDF-SEITE {p['page_number']}{label} | KEIN AUSLESBARER TEXT ({p['quality']})]]\n")
            continue
        block = f"[[PDF-SEITE {p['page_number']}{label}]]\n{p['text'].strip()}\n"
        if used + len(block) > max_chars:
            omitted.append(p["page_number"])
            continue
        parts.append(block)
        used += len(block)
    return "\n".join(parts), omitted


def analyze_study(filename: str, pages: list[dict[str, Any]], heuristics: dict[str, Any],
                  thesis_context: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    doc_text, omitted = build_document_text(pages, config.MAX_TEXT_CHARS)
    system = ANALYSIS_SYSTEM.format(
        criteria=_relevance_criteria(),
        thesis=thesis_context or DEFAULT_THESIS_CONTEXT,
        chapters="; ".join(f"{c['key']} = {c['title']}" for c in CHAPTERS),
    )
    notes = []
    if omitted:
        notes.append(f"ACHTUNG: Wegen Längenbegrenzung fehlen die PDF-Seiten {omitted}. "
                     "Angaben aus diesen Seiten als 'Nicht aus dem Dokument ersichtlich' behandeln.")
    user = (
        f"Dateiname: {filename}\n"
        f"Seitenanzahl: {len(pages)}\n"
        + ("\n".join(notes) + "\n" if notes else "")
        + "Erlaubte Themen-Tags: " + ", ".join(TOPICS) + "\n"
        + "Erlaubte Designkategorien: " + ", ".join(DESIGN_CATEGORIES) + "\n"
        + "Erlaubte Empfehlungen: " + ", ".join(RECOMMENDATIONS) + "\n\n"
        + "<dokument>\n" + doc_text + "\n</dokument>\n\n"
        + "Analysiere die Studie vollständig gemäß Schema. Halte dich strikt an die Regeln."
    )
    data, meta = call_json(system, user, ANALYSIS_SCHEMA, max_tokens=64000)
    if not isinstance(data, dict):
        raise AIError("Unerwartetes Antwortformat der KI.")
    meta["omitted_pages"] = omitted
    return data, meta


# ---------------------------------------------------------------------------
# Synthesen (Vergleich, Theorie, Methodik, Forschungslücken)
# ---------------------------------------------------------------------------

def _cited() -> dict[str, Any]:
    return {"$ref": "#/$defs/cited"}


def _cited_list() -> dict[str, Any]:
    return {"type": "array", "items": {"$ref": "#/$defs/cited"}}


CITED_DEF = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "kind": {"type": "string", "enum": ["literature_finding", "ai_synthesis", "recommendation"]},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"study_id": {"type": "integer"}, "page": {"type": "integer"}},
                "required": ["study_id", "page"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["text", "kind", "citations"],
    "additionalProperties": False,
}


def _schema(props: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "$defs": {"cited": CITED_DEF}, "properties": props,
            "required": list(props), "additionalProperties": False}


COMPARE_SCHEMA = _schema({
    "commonalities": _cited_list(),
    "contradictions": _cited_list(),
    "methodological_differences": _cited_list(),
    "possible_explanations": _cited_list(),
    "caveats": {"type": "string"},
})

THEORY_SCHEMA = _schema({
    "prioritized_sources": {"type": "array", "items": {
        "type": "object", "properties": {"study_id": {"type": "integer"}, "reason": {"type": "string"}},
        "required": ["study_id", "reason"], "additionalProperties": False}},
    "key_insights": _cited_list(),
    "contradictions": _cited_list(),
    "argument_structure": _cited_list(),
    "draft_paragraphs": _cited_list(),
    "missing_literature": {"type": "array", "items": {"type": "string"}},
    "caveats": {"type": "string"},
})

METHODS_SCHEMA = _schema({
    "literature_findings": _cited_list(),
    "recommendations": _cited_list(),
    "open_decisions": {"type": "array", "items": {"type": "string"}},
    "caveats": {"type": "string"},
})

GAPS_SCHEMA = _schema({
    "well_studied": _cited_list(),
    "rarely_studied": _cited_list(),
    "contradictions": _cited_list(),
    "recurring_limitations": _cited_list(),
    "gaps_in_imported_literature": _cited_list(),
    "suggested_search_topics": {"type": "array", "items": {"type": "string"}},
    "caveats": {"type": "string"},
})

SYNTH_RULES = """Regeln:
- Arbeite AUSSCHLIESSLICH mit den gelieferten Studienanalysen (JSON). Keine weiteren Quellen, keine \
Studien aus deinem Vorwissen nennen, keine Zahlen erfinden.
- Jede inhaltliche Aussage (kind "literature_finding") braucht citations mit study_id und physischer \
PDF-Seite (page) aus den gelieferten Daten. Seite 0 nur, wenn keine Seite vorliegt.
- kind "ai_synthesis" = deine eigene Verdichtung/Interpretation; kind "recommendation" = deine eigene \
methodische Empfehlung. Beides klar von Literaturbefunden trennen.
- Wenn die Datenbasis dünn ist, sage das ausdrücklich (caveats).
- Schreibe auf Deutsch, präzise und wissenschaftlich."""


def synthesize(kind: str, task: str, digests: list[dict[str, Any]], schema: dict[str, Any],
               thesis_context: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    system = (
        "Du bist ein wissenschaftlicher Research Assistant für eine sportwissenschaftliche Masterarbeit.\n"
        f"Kontext der Arbeit: {thesis_context or DEFAULT_THESIS_CONTEXT}\n\n{SYNTH_RULES}"
    )
    user = (f"Aufgabe ({kind}):\n{task}\n\n<studienanalysen>\n"
            + json.dumps(digests, ensure_ascii=False) + "\n</studienanalysen>")
    data, meta = call_json(system, user, schema, max_tokens=32000)
    if not isinstance(data, dict):
        raise AIError("Unerwartetes Antwortformat der KI.")
    return data, meta


def test_connection() -> dict[str, Any]:
    client = _client()
    try:
        resp = client.messages.create(
            model=config.CLAUDE_MODEL, max_tokens=2048,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": "Antworte nur mit: OK"}],
        )
    except anthropic.APIStatusError as exc:
        raise AIError(f"API-Fehler {exc.status_code}: {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise AIError("Keine Verbindung zur Claude API.") from exc
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return {"ok": True, "model": resp.model, "reply": text.strip()[:50]}
