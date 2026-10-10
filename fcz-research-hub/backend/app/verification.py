"""Deterministische Überprüfung der KI-Belege gegen den extrahierten PDF-Text.

Die KI liefert zu jeder Angabe Seite + wörtliches Zitat. Hier wird geprüft, ob
das Zitat tatsächlich auf der angegebenen Seite steht. Der Status wird nie
"hochgestuft": Was die KI als unsicher markiert, bleibt unsicher; ein nicht
auffindbares Zitat wird auf "uncertain" herabgestuft."""
from __future__ import annotations

from typing import Any, Iterator

from .pdf_processing import normalize_text
from .schema import NOT_REPORTED

FUZZY_VERIFIED = 0.85
FUZZY_UNCERTAIN = 0.6

_NOT_REPORTED_MARKERS = (
    "nicht berichtet", "nicht aus dem dokument ersichtlich", "not reported", "keine angabe",
)


def _trigrams(words: list[str]) -> set[tuple[str, ...]]:
    if len(words) < 3:
        return {tuple(words)} if words else set()
    return {tuple(words[i:i + 3]) for i in range(len(words) - 2)}


class PageIndex:
    def __init__(self, pages: list[dict[str, Any]]):
        self.norm: dict[int, str] = {}
        self.tri: dict[int, set[tuple[str, ...]]] = {}
        self.labels: dict[int, str | None] = {}
        for p in pages:
            n = p["page_number"]
            t = normalize_text(p["text"])
            self.norm[n] = t
            self.tri[n] = _trigrams(_words(t))
            self.labels[n] = p.get("page_label")
        self.page_count = len(pages)

    def locate(self, quote: str, page_hint: int) -> dict[str, Any]:
        q = normalize_text(quote)
        if len(q) < 8:
            return {"quote_check": "too_short", "page": page_hint or None, "coverage": 0.0}
        order = ([page_hint] if page_hint in self.norm else []) + [n for n in self.norm if n != page_hint]
        for n in order:
            if q in self.norm[n]:
                return {"quote_check": "exact", "page": n, "coverage": 1.0}
        qt = _trigrams(_words(q))
        best_n, best_cov = None, 0.0
        if qt:
            for n in order:
                cov = len(qt & self.tri[n]) / len(qt)
                if cov > best_cov:
                    best_n, best_cov = n, cov
        if best_n is not None and best_cov >= FUZZY_UNCERTAIN:
            return {"quote_check": "fuzzy", "page": best_n, "coverage": round(best_cov, 2)}
        return {"quote_check": "not_found", "page": page_hint or None, "coverage": round(best_cov, 2)}


def _words(s: str) -> list[str]:
    return [w.strip(".,;:()[]{}\"'") for w in s.split() if w.strip(".,;:()[]{}\"'")]


def is_not_reported(value: str) -> bool:
    v = (value or "").strip().lower()
    return v == "" or any(v.startswith(m) for m in _NOT_REPORTED_MARKERS)


def _verify_item(item: dict[str, Any], index: PageIndex, value_key: str = "value") -> None:
    value = str(item.get(value_key, "") or "")
    source_type = item.get("source_type", "author_statement")
    status = item.get("status", "uncertain")
    quote = (item.get("quote") or "").strip()
    page = item.get("page") or 0
    check: dict[str, Any] = {}

    if status == "not_reported" or (value_key == "value" and is_not_reported(value)):
        item["status"] = "not_reported"
        if is_not_reported(value):
            item[value_key] = value or NOT_REPORTED
        check = {"quote_check": "no_quote"}
        item["page"] = page if quote else 0
    elif not quote:
        check = {"quote_check": "no_quote"}
        if source_type == "author_statement":
            item["status"] = "uncertain"
            check["note"] = "Kein Originalzitat geliefert – Angabe bitte im PDF prüfen."
    else:
        res = index.locate(quote, page)
        check = {"quote_check": res["quote_check"], "coverage": res["coverage"]}
        if res["page"] and res["page"] != page:
            check["page_corrected_from"] = page
            item["page"] = res["page"]
        if res["quote_check"] == "exact":
            pass  # Status der KI bleibt (verified bleibt verified, uncertain bleibt uncertain)
        elif res["quote_check"] == "fuzzy" and res["coverage"] >= FUZZY_VERIFIED:
            check["note"] = "Zitat sinngemäß/nahezu wörtlich gefunden (Abweichungen z. B. durch Zeilenumbrüche/Sonderzeichen)."
        else:
            if status == "verified":
                item["status"] = "uncertain"
            check["note"] = ("Zitat nicht wörtlich im extrahierten Text gefunden – "
                             "bitte im PDF prüfen." if res["quote_check"] != "too_short"
                             else "Zitat zu kurz für eine Prüfung.")
    pg = item.get("page") or 0
    if pg and pg > index.page_count:
        check["note"] = "Angegebene Seite existiert im PDF nicht."
        item["status"] = "uncertain"
        item["page"] = 0
        pg = 0
    item["page_label"] = index.labels.get(pg) if pg else None
    item["check"] = check


def iter_claims(node: Any, path: str = "") -> Iterator[tuple[str, dict[str, Any]]]:
    if isinstance(node, dict):
        if "value" in node and "quote" in node and "status" in node:
            yield path, node
            return
        for k, v in node.items():
            yield from iter_claims(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from iter_claims(v, f"{path}[{i}]")


def verify_analysis(analysis: dict[str, Any], pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Prüft alle Claims und Variablen; ergänzt gedruckte Seitenzahlen. In-place."""
    index = PageIndex(pages)
    stats = {"claims": 0, "verified": 0, "uncertain": 0, "not_reported": 0,
             "quote_exact": 0, "quote_fuzzy": 0, "quote_not_found": 0, "page_corrected": 0}
    for _, claim in iter_claims(analysis):
        _verify_item(claim, index)
        _count(stats, claim)
    for var in analysis.get("variables", []) or []:
        var.setdefault("source_type", "author_statement")
        var["value"] = var.get("name", "")
        _verify_item(var, index)
        var.pop("value", None)
        _count(stats, var)
    analysis["verification"] = stats
    return stats


def _count(stats: dict[str, int], item: dict[str, Any]) -> None:
    stats["claims"] += 1
    stats[item.get("status", "uncertain")] = stats.get(item.get("status", "uncertain"), 0) + 1
    qc = item.get("check", {}).get("quote_check")
    if qc == "exact":
        stats["quote_exact"] += 1
    elif qc == "fuzzy":
        stats["quote_fuzzy"] += 1
    elif qc == "not_found":
        stats["quote_not_found"] += 1
    if "page_corrected_from" in item.get("check", {}):
        stats["page_corrected"] += 1


def evidence_rows(study_id: int, analysis: dict[str, Any]) -> list[tuple]:
    rows = []
    for path, c in iter_claims(analysis):
        rows.append((study_id, path, str(c.get("value", "")), c.get("page") or None,
                     c.get("page_label"), c.get("quote") or None, c.get("status", "uncertain"),
                     c.get("source_type", "author_statement"), c.get("check", {}).get("quote_check")))
    for i, v in enumerate(analysis.get("variables", []) or []):
        stmt = f"{v.get('name', '')}: {v.get('definition', '')}"
        rows.append((study_id, f"variables[{i}]", stmt, v.get("page") or None, v.get("page_label"),
                     v.get("quote") or None, v.get("status", "uncertain"), "author_statement",
                     v.get("check", {}).get("quote_check")))
    return rows
