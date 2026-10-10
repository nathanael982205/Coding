"""PDF-Verarbeitung mit PyMuPDF: Textextraktion, Qualitätsprüfung (OCR-Erkennung),
Seitenzahlen (physisch vs. gedruckt), regelbasierte Vorab-Erkennung und
Koordinaten für Textmarkierungen im PDF-Viewer."""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import pymupdf

# Schwellenwerte für die Seitenqualität
MIN_CHARS_OK = 200
MIN_CHARS_TEXT = 30

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.IGNORECASE)

# Regelbasierte Begriffslisten (nur zur Vorab-Orientierung, keine KI)
KEYWORD_GROUPS: dict[str, list[str]] = {
    "gps": ["gps", "gnss", "global positioning", "wimu", "catapult", "statsports",
            "high-speed running", "high speed running", "sprint distance",
            "total distance", "accelerations", "decelerations", "playerload",
            "player load", "external load", "tracking system", "lps", "local positioning"],
    "cmj": ["countermovement jump", "counter-movement jump", "counter movement jump",
            "cmj", "forcedecks", "force plate", "force platform", "jump height",
            "rsimod", "rsi-mod", "flight time:contraction time", "ft:ct"],
    "football": ["soccer", "football", "fußball", "futbol"],
    "fatigue": ["neuromuscular fatigue", "neuromuscular function", "readiness",
                "recovery", "md+1", "md+2", "md+3", "match day", "post-match", "postmatch"],
    "internal_load": ["rpe", "session-rpe", "srpe", "wellness", "heart rate", "trimp",
                      "creatine kinase", "ck "],
}


def sanitize_filename(name: str) -> str:
    name = Path(name).name
    name = unicodedata.normalize("NFC", name)
    name = re.sub(r"[^\w.\- ()\[\]äöüÄÖÜß,&+]", "_", name)
    name = name.strip(" .") or "dokument.pdf"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name[:180]


def normalize_text(s: str) -> str:
    """Normalisierung für robuste Zitatprüfung/Suche."""
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("­", "")  # weiches Trennzeichen
    s = re.sub(r"-\s*\n\s*", "", s)  # Silbentrennung am Zeilenende
    trans = {
        "‘": "'", "’": "'", "“": '"', "”": '"', "„": '"',
        "–": "-", "—": "-", "−": "-", " ": " ", " ": " ",
        "±": "+/-",
    }
    for a, b in trans.items():
        s = s.replace(a, b)
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _page_quality(chars: int, has_images: bool, text: str) -> str:
    if chars >= MIN_CHARS_OK:
        bad = sum(1 for c in text if c == "�" or (unicodedata.category(c) in {"Co", "Cn"}))
        if bad / max(chars, 1) > 0.15:
            return "garbled"
        return "ok"
    if chars >= MIN_CHARS_TEXT:
        return "low_text"
    return "scanned" if has_images else "empty"


def _candidate_printed_number(page: pymupdf.Page) -> int | None:
    """Sucht eine allein stehende Seitenzahl in Kopf- oder Fußzeile."""
    blocks = page.get_text("blocks")
    if not blocks:
        return None
    h = page.rect.height
    margin = []
    for b in blocks:
        x0, y0, x1, y1, txt = b[0], b[1], b[2], b[3], b[4]
        if y1 < h * 0.1 or y0 > h * 0.9:
            margin.append(txt)
    for txt in margin:
        for line in txt.splitlines():
            line = line.strip()
            m = re.fullmatch(r"(?:page\s+|seite\s+|s\.\s*)?(\d{1,4})", line, re.IGNORECASE)
            if m:
                return int(m.group(1))
            m = re.search(r"(?:^|\s)(\d{1,4})\s*$", line)
            if m and len(line) < 120:
                # z. B. "Journal of Sports Sciences 245" -> nur wenn kurz
                return int(m.group(1))
    return None


def extract_pdf(path: Path) -> dict[str, Any]:
    """Extrahiert Seitentexte, Seitenlabels, Qualitätsmetriken und Metadaten.

    Wirft ValueError mit verständlicher Meldung bei beschädigten/verschlüsselten PDFs.
    """
    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"PDF konnte nicht geöffnet werden (beschädigt oder kein PDF): {exc}") from exc

    with doc:
        if doc.needs_pass:
            raise ValueError("PDF ist passwortgeschützt und kann nicht ausgelesen werden.")
        if doc.page_count == 0:
            raise ValueError("PDF enthält keine Seiten.")

        has_labels = False
        try:
            has_labels = bool(doc.get_page_labels())
        except Exception:  # noqa: BLE001
            has_labels = False

        pages: list[dict[str, Any]] = []
        candidates: list[tuple[int, int]] = []
        flags = pymupdf.TEXTFLAGS_TEXT | pymupdf.TEXT_DEHYPHENATE
        for i, page in enumerate(doc):
            try:
                text = page.get_text("text", flags=flags, sort=True) or ""
            except Exception:  # noqa: BLE001
                text = ""
            text = text.replace("\x00", "")
            chars = len(re.sub(r"\s", "", text))
            try:
                has_images = len(page.get_images(full=False)) > 0
            except Exception:  # noqa: BLE001
                has_images = False
            quality = _page_quality(chars, has_images, text)
            label = None
            label_source = None
            if has_labels:
                try:
                    label = page.get_label() or None
                    label_source = "pdf_label" if label else None
                except Exception:  # noqa: BLE001
                    label = None
            if not label:
                cand = _candidate_printed_number(page)
                if cand is not None:
                    candidates.append((i + 1, cand))
            pages.append({
                "page_number": i + 1,
                "page_label": label,
                "label_source": label_source,
                "text": text,
                "char_count": chars,
                "quality": quality,
            })

        # Gedruckte Seitenzahlen über konsistenten Versatz ableiten
        if candidates:
            offsets = Counter(c - p for p, c in candidates)
            offset, freq = offsets.most_common(1)[0]
            needed = max(2, int(0.4 * len(pages)))
            if freq >= needed or (len(pages) <= 3 and freq >= 1):
                for pg in pages:
                    if not pg["page_label"] and pg["page_number"] + offset > 0:
                        pg["page_label"] = str(pg["page_number"] + offset)
                        pg["label_source"] = "heuristic"

        meta = {k: v for k, v in (doc.metadata or {}).items() if v}

    q = Counter(p["quality"] for p in pages)
    total_chars = sum(p["char_count"] for p in pages)
    scanned = [p["page_number"] for p in pages if p["quality"] in {"scanned", "garbled"}]
    low = [p["page_number"] for p in pages if p["quality"] in {"low_text", "empty"}]
    n = len(pages)
    if total_chars < 500 or len(scanned) >= max(1, n * 0.5):
        overall = "needs_ocr"
    elif scanned:
        overall = "partial"
    else:
        overall = "ok"
    text_quality = {
        "overall": overall,
        "page_count": n,
        "total_chars": total_chars,
        "pages_ok": q.get("ok", 0),
        "pages_low_text": q.get("low_text", 0),
        "pages_scanned": q.get("scanned", 0),
        "pages_garbled": q.get("garbled", 0),
        "pages_empty": q.get("empty", 0),
        "scanned_pages": scanned,
        "low_text_pages": low,
        "printed_page_source": (
            "pdf_label" if has_labels else ("heuristic" if any(p["label_source"] == "heuristic" for p in pages) else "none")
        ),
        "hint": _quality_hint(overall, scanned, low),
    }
    return {"pages": pages, "text_quality": text_quality, "metadata": meta}


def _quality_hint(overall: str, scanned: list[int], low: list[int]) -> str:
    if overall == "needs_ocr":
        return ("Das PDF enthält (fast) keinen maschinenlesbaren Text – vermutlich eingescannt. "
                "Bitte zuerst OCR durchführen (z. B. `ocrmypdf input.pdf output.pdf`) und erneut importieren.")
    if overall == "partial":
        return (f"Seiten ohne auslesbaren Text (vermutlich Scan/Abbildung): {', '.join(map(str, scanned))}. "
                "Inhalte dieser Seiten fließen nicht in die Analyse ein.")
    if low:
        return (f"Seiten mit wenig Text (z. B. Abbildungen/Tabellen als Bild): {', '.join(map(str, low[:20]))}.")
    return "Text auf allen Seiten erfolgreich extrahiert."


def heuristic_scan(pages: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
    """Regelbasierte Vorab-Erkennung ohne KI. Ergebnisse sind ungeprüft."""
    full = "\n".join(p["text"] for p in pages)
    low = full.lower()
    doi = None
    m = DOI_RE.search(full[:20000])
    if m:
        doi = m.group(1).rstrip(".,;)]")
    hits: dict[str, dict[str, Any]] = {}
    for group, terms in KEYWORD_GROUPS.items():
        total = 0
        first_page = None
        found_terms = []
        for t in terms:
            c = low.count(t)
            if c:
                total += c
                found_terms.append(t)
        if total:
            for p in pages:
                pl = p["text"].lower()
                if any(t in pl for t in found_terms):
                    first_page = p["page_number"]
                    break
        hits[group] = {"count": total, "terms": found_terms[:8], "first_page": first_page}
    title = (metadata.get("title") or "").strip()
    if len(title) < 15 or title.lower().endswith((".doc", ".docx", ".pdf")) or "microsoft" in title.lower():
        title = ""
    years = re.findall(r"\b(19[89]\d|20[0-3]\d)\b", "\n".join(p["text"] for p in pages[:2]))
    return {
        "source": "regelbasiert (keine KI, ungeprüft)",
        "doi": doi,
        "title_from_metadata": title or None,
        "author_from_metadata": metadata.get("author") or None,
        "year_candidates": sorted(set(years))[-5:],
        "keyword_hits": hits,
    }


def _quote_chunks(quote: str, words_per_chunk: int = 7) -> list[str]:
    words = quote.split()
    if len(words) <= words_per_chunk + 2:
        return [quote]
    return [" ".join(words[i:i + words_per_chunk]) for i in range(0, len(words), words_per_chunk)
            if len(words[i:i + words_per_chunk]) >= 3]


def find_highlights(path: Path, page_number: int, query: str, max_hits: int = 60) -> dict[str, Any]:
    """Liefert Rechtecke (PDF-Koordinaten) für Text auf einer Seite."""
    query = (query or "").strip()
    with pymupdf.open(path) as doc:
        if page_number < 1 or page_number > doc.page_count:
            return {"page": page_number, "rects": [], "width": 0, "height": 0}
        page = doc[page_number - 1]
        rects: list[list[float]] = []
        if query:
            q = unicodedata.normalize("NFKC", query)
            for chunk in _quote_chunks(q):
                for r in page.search_for(chunk, quads=False)[:max_hits]:
                    if page.rotation:
                        r = r * page.rotation_matrix
                    rects.append([r.x0, r.y0, r.x1, r.y1])
        return {"page": page_number, "rects": rects,
                "width": page.rect.width, "height": page.rect.height}
