"""OpenAI-Anbindung (ChatGPT-/GPT-Modelle über die Responses API) als Alternative zu Claude.

Gleiche Schnittstelle wie llm.call_json: strukturierte JSON-Ausgabe nach Schema.
Der API-Schlüssel bleibt im Backend. Es werden nur Texte der importierten
wissenschaftlichen PDFs bzw. daraus abgeleitete Analysen übertragen."""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

import openai

from . import config
from .llm import AIError, AIUnavailable, _extract_json

log = logging.getLogger("research_hub.llm_openai")

# Bei Rate-Limits (nicht bei fehlendem Guthaben) automatisch warten und erneut versuchen.
RATE_LIMIT_RETRIES = 8
# Nur eine OpenAI-Anfrage gleichzeitig – schont niedrige Limits neuer Konten.
_request_lock = threading.Semaphore(1)


def _is_quota_error(exc: openai.RateLimitError) -> bool:
    body = exc.body if isinstance(exc.body, dict) else {}
    err = body.get("error", body) if isinstance(body, dict) else {}
    code = (err.get("code") or err.get("type") or "") if isinstance(err, dict) else ""
    detail = ((err.get("message") if isinstance(err, dict) else None) or str(exc.message)).lower()
    return code == "insufficient_quota" or "quota" in detail


def _wait_seconds(exc: openai.RateLimitError, attempt: int) -> float:
    try:
        ra = exc.response.headers.get("retry-after")
        if ra:
            return min(max(float(ra), 5.0), 120.0)
    except Exception:  # noqa: BLE001
        pass
    return min(20.0 * (attempt + 1), 120.0)


def _create(client: openai.OpenAI, kwargs: dict[str, Any]):
    """responses.create mit Warten bei Rate-Limits (Guthabenfehler werden sofort gemeldet)."""
    for attempt in range(RATE_LIMIT_RETRIES):
        try:
            with _request_lock:
                return client.responses.create(**kwargs)
        except openai.RateLimitError as exc:
            too_large = "request too large" in str(exc.message).lower()
            if _is_quota_error(exc) or too_large or attempt == RATE_LIMIT_RETRIES - 1:
                raise
            wait = _wait_seconds(exc, attempt)
            log.warning("OpenAI-Rate-Limit – warte %.0f s (Versuch %d/%d): %s",
                        wait, attempt + 1, RATE_LIMIT_RETRIES, exc.message)
            time.sleep(wait)
    raise AIError("Rate-Limit: zu viele Versuche.")


def _client() -> openai.OpenAI:
    if not config.OPENAI_API_KEY:
        raise AIUnavailable("Kein OPENAI_API_KEY in .env konfiguriert – KI-Funktionen sind deaktiviert.")
    return openai.OpenAI(api_key=config.OPENAI_API_KEY, max_retries=3, timeout=900)


def _explain_429(exc: openai.RateLimitError) -> str:
    """Unterscheidet fehlendes Guthaben von Rate-Limits und gibt die Originalmeldung weiter."""
    body = exc.body if isinstance(exc.body, dict) else {}
    err = body.get("error", body) if isinstance(body, dict) else {}
    detail = (err.get("message") if isinstance(err, dict) else None) or str(exc.message)
    if _is_quota_error(exc):
        return ("OpenAI meldet: kein nutzbares Guthaben (insufficient_quota). Prüfen Sie unter platform.openai.com → "
                "Billing, ob das Guthaben gebucht ist und ob der API-Schlüssel zum selben Projekt/zur selben "
                f"Organisation gehört. Neu eingezahltes Guthaben kann einige Minuten brauchen. Originalmeldung: {detail}")
    if "request too large" in detail.lower():
        return ("OpenAI (429): Diese Studie ist für das Token-pro-Minute-Limit Ihres Kontos zu groß – Warten hilft "
                "hier nicht. Lösungen: in .env HUB_OPENAI_MAX_OUTPUT=16000 setzen, ein Modell mit höherem Limit "
                "wählen (HUB_OPENAI_MODEL) oder abwarten, bis OpenAI Ihr Konto auf eine höhere Stufe hebt "
                f"(platform.openai.com → Limits). Originalmeldung: {detail}")
    return ("OpenAI-Rate-Limit (429): Die Anfrage ist größer als das Token-pro-Minute-Limit Ihres Kontos "
            "(neue Konten haben niedrige Limits, siehe platform.openai.com → Limits). Tipp: in .env "
            "ANALYSIS_WORKERS=1 und HUB_OPENAI_MAX_OUTPUT=16000 setzen und später erneut versuchen. "
            f"Originalmeldung: {detail}")


def call_json(system: str, user_content: str, schema: dict[str, Any],
              max_tokens: int = 64000) -> tuple[Any, dict[str, Any]]:
    client = _client()
    use_schema = True
    use_reasoning = bool(config.OPENAI_EFFORT)
    last_exc: Exception | None = None
    for _attempt in range(3):
        instructions = system
        kwargs: dict[str, Any] = {
            "model": config.OPENAI_MODEL,
            "input": [{"role": "user", "content": user_content}],
            "max_output_tokens": min(max_tokens, config.OPENAI_MAX_OUTPUT),
            "store": False,
        }
        if use_schema:
            kwargs["text"] = {"format": {"type": "json_schema", "name": "analyse", "schema": schema, "strict": True}}
        else:
            instructions = (system + "\n\nAntworte ausschließlich mit einem JSON-Objekt, das exakt diesem "
                            "JSON-Schema entspricht (keine Erklärungen, kein Markdown):\n" + json.dumps(schema))
            kwargs["text"] = {"format": {"type": "json_object"}}
        kwargs["instructions"] = instructions
        if use_reasoning:
            kwargs["reasoning"] = {"effort": config.OPENAI_EFFORT}
        try:
            resp = _create(client, kwargs)
        except openai.AuthenticationError as exc:
            raise AIError("OpenAI-API-Schlüssel ungültig (401). Bitte OPENAI_API_KEY in .env prüfen.") from exc
        except openai.PermissionDeniedError as exc:
            raise AIError(f"Zugriff verweigert (403): {exc.message}") from exc
        except openai.NotFoundError as exc:
            raise AIError(f"Modell '{config.OPENAI_MODEL}' nicht gefunden (404). HUB_OPENAI_MODEL prüfen.") from exc
        except openai.BadRequestError as exc:
            last_exc = exc
            msg_l = str(exc.message).lower()
            if use_reasoning and ("reasoning" in msg_l or "effort" in msg_l):
                log.warning("Reasoning-Parameter abgelehnt, erneuter Versuch ohne: %s", exc.message)
                use_reasoning = False
                continue
            if use_schema and ("schema" in msg_l or "json_schema" in msg_l or "format" in msg_l):
                log.warning("JSON-Schema abgelehnt, erneuter Versuch mit Schema im Prompt: %s", exc.message)
                use_schema = False
                continue
            raise AIError(f"Ungültige Anfrage (400): {exc.message}") from exc
        except openai.RateLimitError as exc:
            raise AIError(_explain_429(exc)) from exc
        except openai.APIStatusError as exc:
            raise AIError(f"API-Fehler {exc.status_code}: {exc.message}") from exc
        except openai.APIConnectionError as exc:
            raise AIError("Keine Verbindung zur OpenAI API (Netzwerk/Proxy prüfen).") from exc

        if getattr(resp, "status", None) == "incomplete":
            reason = getattr(getattr(resp, "incomplete_details", None), "reason", None)
            if reason == "content_filter":
                raise AIError("Die Anfrage wurde vom Inhaltsfilter abgelehnt.")
            raise AIError(f"Antwort unvollständig ({reason}) – Analyse abgebrochen.")
        for item in getattr(resp, "output", []) or []:
            for c in getattr(item, "content", None) or []:
                if getattr(c, "type", "") == "refusal":
                    raise AIError(f"Die Anfrage wurde vom Modell abgelehnt: {getattr(c, 'refusal', '')}")
        text = resp.output_text or ""
        try:
            data = _extract_json(text)
        except (ValueError, json.JSONDecodeError) as exc:
            last_exc = exc
            if use_schema:
                raise AIError("Antwort war kein gültiges JSON.") from exc
            continue
        usage = getattr(resp, "usage", None)
        meta = {
            "model": getattr(resp, "model", config.OPENAI_MODEL),
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "structured_output": use_schema,
        }
        return data, meta
    raise AIError(f"KI-Aufruf fehlgeschlagen: {last_exc}")


def test_connection() -> dict[str, Any]:
    client = _client()
    try:
        resp = client.responses.create(model=config.OPENAI_MODEL, input="Antworte nur mit: OK",
                                       max_output_tokens=2048, store=False)
    except openai.APIStatusError as exc:
        raise AIError(f"API-Fehler {exc.status_code}: {exc.message}") from exc
    except openai.APIConnectionError as exc:
        raise AIError("Keine Verbindung zur OpenAI API.") from exc
    return {"ok": True, "model": resp.model, "reply": (resp.output_text or "").strip()[:50]}
