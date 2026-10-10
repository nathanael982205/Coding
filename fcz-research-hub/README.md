# FCZ Thesis Research Hub

Lokale Webanwendung für die Literaturarbeit der Masterarbeit *„GPS-basierte externe Belastung und neuromuskuläre Readiness (CMJ) professioneller Fußballspieler 24–72 h nach Belastung“* (Kooperation FC Zürich).

Sie importieren wissenschaftliche PDFs. Die App extrahiert den Text seitengenau, lässt jede Studie von einer KI – wahlweise **Claude (Anthropic)** oder **ChatGPT/GPT (OpenAI)** – strukturiert analysieren und prüft danach jede Angabe automatisch gegen den PDF-Text. Das Ergebnis ist eine durchsuchbare Literaturdatenbank mit Dashboard, Literaturmatrix, Studienvergleich, Theorie- und Methodik-Assistent sowie einer Lückenanalyse.

---

## 1. Schnellstart

Voraussetzung: Python 3.10 oder neuer.

```bash
cd fcz-research-hub
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
cp .env.example .env          # Windows: copy .env.example .env
# .env öffnen, HUB_PROVIDER wählen und den passenden Schlüssel eintragen (optional, siehe unten)

python run.py                 # öffnet http://localhost:8000
```

Mit `python run.py --no-browser` startet der Server, ohne den Browser zu öffnen. Beenden mit `Strg+C`.

**Ohne API-Schlüssel** startet die App ebenfalls. PDFs werden dann importiert, der Text wird extrahiert und ist durchsuchbar, und bereits gespeicherte Analysen bleiben vollständig nutzbar. Die KI-Analyse läuft, sobald ein Schlüssel eingetragen und der Server neu gestartet ist (Einstellungen → „Ausstehende analysieren“). Ist die Bibliothek leer, zeigt die App eine deutlich als **DEMO** markierte Beispielansicht mit Platzhaltern.

Die Oberfläche funktioniert offline. PDF.js und Chart.js liegen lokal unter `frontend/vendor/`. Internet braucht nur die KI-Analyse.

---

## 2. Funktionen

| Bereich | Was er kann |
|---|---|
| **PDF-Import** | Drag & Drop mehrerer PDFs, Upload-Fortschritt pro Datei, Speicherung unter dem Originalnamen, Dublettenerkennung über den Dateiinhalt (SHA-256) und zusätzlich ein Hinweis bei gleicher DOI, Erkennung defekter, passwortgeschützter und eingescannter PDFs |
| **Textextraktion** | Seitenweise mit PyMuPDF. Jede Seite wird klassifiziert (`ok`, `low_text`, `scanned`, `garbled`, `empty`). Ist ein PDF überwiegend gescannt, erscheint der Hinweis „OCR nötig“ samt Befehl |
| **KI-Analyse** | Abschnitte A–G (Bibliografie, Design, Stichprobe, Methodik, Variablen, Ergebnisse, Statistik, Kritik, Relevanz) mit Seitenbeleg und Originalzitat zu jeder Angabe |
| **Nachvollziehbarkeit** | Automatische Zitatprüfung gegen den PDF-Text. Status *verifiziert / unsicher / nicht berichtet*. Kennzeichnung, ob eine Angabe von den Autoren stammt, eine KI-Zusammenfassung oder eine KI-Bewertung ist. Physische und gedruckte Seitenzahl werden getrennt geführt |
| **Dashboard** | KPI-Karten und Diagramme, berechnet ausschließlich aus den importierten Studien |
| **Studienbibliothek** | Karten- oder Tabellenansicht, 14 Filter, FTS5-Volltextsuche über Titel, Analysen, Notizen und PDF-Text, mit Trefferstellen |
| **Detailansicht** | Links die Analyse in 9 Tabs, rechts das PDF. Ein Klick auf eine Quelle springt zur Seite und markiert die Textstelle. Dazu Notizen, Markierungen (Sehr wichtig, Relevant, Später lesen, Gelesen, Für Methodik, Für Diskussion) und eine anpassbare Kapitelzuordnung |
| **Literaturmatrix** | Sortierbar, filterbar, Spalten wählbar. Export als Excel (mit Blatt „Belege“), CSV, JSON, BibTeX, RIS |
| **Studienvergleich** | 2–5 Studien nebeneinander mit Markierung von Übereinstimmungen und Unterschieden, dazu eine KI-Synthese mit geprüften Belegen |
| **Theorie-Assistent** | 7 Kapitel: priorisierte Quellen, Kapitelnotizen, KI-Synthese (Erkenntnisse, Widersprüche, Argumentationsstruktur, belegter Textentwurf, fehlende Aspekte), Word-Export |
| **Methodik-Assistent** | 12 Themen von Design bis Mixed-Effects-Modelle. Literaturbefunde mit Belegen stehen getrennt von den KI-Empfehlungen, dazu eigene Entscheidungsnotizen |
| **Forschungslücken** | Deterministische Zählungen (GPS- und CMJ-Parameter einschließlich nie untersuchter, Zeitpunkte 24/48/72 h, Profifußball, GPS+CMJ, Limitationen) und eine KI-Lückenanalyse, ausdrücklich beschränkt auf die importierte Literatur |
| **Datenhaltung** | SQLite, Backup als ZIP (Datenbank + PDFs), Wiederherstellung mit automatischer Sicherung des aktuellen Stands |

---

## 3. Technische Entscheidungen

| Entscheidung | Begründung |
|---|---|
| **FastAPI + SQLite** | Ein Prozess, keine Datenbankinstallation. Eine Datei genügt für Backups. FTS5 liefert eine schnelle Volltextsuche ohne Zusatzdienst |
| **PyMuPDF** | Schnelle, robuste Extraktion pro Seite, Seitenlabels, Bilderkennung für die OCR-Diagnose und Koordinaten für die Markierungen im Viewer (`search_for`) |
| **Zwei KI-Anbieter zur Wahl** | `HUB_PROVIDER=anthropic` (Claude, offizielles `anthropic`-SDK) oder `HUB_PROVIDER=openai` (GPT-Modelle über die OpenAI Responses API mit Structured Outputs, `backend/app/llm_openai.py`). Prompts, Schema, Zitatprüfung und alle Auswertungen sind für beide identisch |
| **Claude über das offizielle `anthropic`-SDK** | Structured Outputs (JSON-Schema) erzwingen das Analyseformat. Streaming verhindert Timeouts bei langen Analysen. Der Refusal-Fallback ist aktiv und abschaltbar. Standardmodell: `claude-opus-5-5`, Effort `high` |
| **Text mit Seitenmarkern statt PDF-Upload an die API** | Die KI erhält `[[PDF-SEITE n \| gedruckte Seite: x]]` vor jeder Seite. So sind Seitenangaben eindeutig physische Seiten und lassen sich gegen genau denselben Text prüfen. Eingescannte Seiten werden ausdrücklich als „kein auslesbarer Text“ markiert, statt dass die KI rät |
| **Eigenes CSS statt Tailwind** | Kein Build-Schritt und kein CDN. Design-Tokens als CSS-Variablen machen den Dark Mode trivial |
| **Vanilla-JS-Module** | Keine Toolchain: Dateien bearbeiten, Seite neu laden |
| **Deterministische Berechnungen im Backend** | Relevanz-Gesamtscore, Zitatprüfung, Kennzahlen und Lückenzählungen sind Code, keine KI-Ausgabe |

---

## 4. Wissenschaftliche Nachvollziehbarkeit

Jede inhaltliche Angabe ist ein **Claim**:

```json
{
  "value": "20 professionelle Fußballspieler",
  "page": 2,
  "page_label": "102",
  "quote": "Twenty professional soccer players participated",
  "status": "verified",
  "source_type": "author_statement",
  "check": { "quote_check": "exact", "coverage": 1.0 }
}
```

- **`page`** ist die physische PDF-Seite (1-basiert). **`page_label`** ist die gedruckte Seitenzahl, sofern erkennbar, entweder aus PDF-Seitenlabels oder aus Kopf- und Fußzeilen abgeleitet (in der Oberfläche als „abgeleitet“ gekennzeichnet).
- **`status`**: `verified`, `uncertain` oder `not_reported`. Fehlende Informationen heißen ausdrücklich „Nicht berichtet“.
- **`source_type`**: `author_statement` (Aussage der Autoren), `ai_summary` (KI-Zusammenfassung) oder `ai_assessment` (methodische KI-Bewertung).
- **Zitatprüfung** (`backend/app/verification.py`):
  - Das Zitat wird normalisiert (Ligaturen, Silbentrennung, Anführungszeichen, Leerraum) und zuerst auf der angegebenen Seite gesucht, dann auf allen anderen Seiten.
  - `exact`: wörtlich gefunden. Steht das Zitat auf einer anderen Seite, wird die Seite korrigiert und das in der Oberfläche angezeigt.
  - `fuzzy`: mindestens 85 % der Wort-Trigramme stimmen überein.
  - `not_found`: Der Status wird auf **unsicher** herabgestuft.
  - Ein Status wird nie hochgestuft.
  - Autorenangaben ohne Zitat werden als unsicher markiert.
- **KI-Synthesen** (Vergleich, Theorie, Methodik, Lücken) zitieren `study_id + page`. Jeder Beleg wird geprüft: Studie in der Auswahl? Seite vorhanden? Seite durch eine Analyseangabe gedeckt? Ungültige Belege erscheinen rot, schwache gelb, Aussagen ohne Beleg werden markiert.
- **Textentwürfe** sind immer als „KI-Entwurf – ungeprüft“ gekennzeichnet.

### Relevanz-Score

`0,30 · Thematik + 0,25 · Methodik + 0,15 · Stichprobe + 0,20 · Variablen + 0,10 · Theorie`

Die KI vergibt die Teilscores (0–100) mit Begründung. Den Gesamtwert berechnet das Backend. Der Score ist eine **interne Einschätzung der Passung zur Masterarbeit, keine Bewertung der wissenschaftlichen Qualität**. Den Kontext der Arbeit, an dem sich die Bewertung orientiert, können Sie unter *Einstellungen* anpassen.

---

## 5. Projektstruktur und Datenstruktur

```
fcz-research-hub/
├── run.py                    # Startskript (http://localhost:8000)
├── requirements.txt
├── .env.example              # Vorlage für .env (API-Schlüssel nur hier)
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI-Routen + Auslieferung des Frontends
│   │   ├── config.py         # Einstellungen aus .env
│   │   ├── db.py             # SQLite-Schema, FTS5
│   │   ├── pdf_processing.py # Extraktion, OCR-Erkennung, Seitenzahlen, Markierungen
│   │   ├── schema.py         # Analyseschema, Vokabulare, Relevanzgewichte
│   │   ├── llm.py            # Claude-Anbindung, Prompts, Synthese-Schemata
│   │   ├── verification.py   # Zitatprüfung und Belegtabelle
│   │   ├── services.py       # Import, Analyse, Suche, Kennzahlen, Lückenzählung
│   │   ├── assistants.py     # Vergleich, Theorie-, Methodik-, Lücken-Assistent
│   │   ├── exports.py        # CSV/XLSX/JSON/DOCX/BibTeX/RIS, Backup/Restore
│   │   ├── jobs.py           # Hintergrund-Analysen (Thread-Pool)
│   │   └── demo.py           # fiktive DEMO-Platzhalter (werden nie gespeichert)
│   └── tests/smoke_test.py   # Rauchtest ohne API-Schlüssel
├── frontend/
│   ├── index.html
│   ├── css/app.css
│   ├── js/                   # app.js (Router), api.js, ui.js, pdfviewer.js, charts.js, views/*.js
│   └── vendor/               # PDF.js 3.11.174, Chart.js 4.4.4 (lokal, mit Lizenzen)
├── sample/
│   ├── make_test_pdf.py      # erzeugt ein synthetisches Test-PDF
│   └── beispiel_analyse.json # Beispielstruktur einer gespeicherten Analyse (synthetisch)
└── data/                     # wird automatisch angelegt (in .gitignore)
    ├── research_hub.sqlite3
    ├── pdfs/                 # importierte PDFs (Originalname, bei Namensgleichheit „(2)“)
    └── backups/
```

### Datenbanktabellen (`backend/app/db.py`)

| Tabelle | Inhalt |
|---|---|
| `studies` | Datei, SHA-256, Status, Textqualität, flache Filterfelder (Jahr, Design, n, Niveau, GPS/CMJ, Relevanz …), vollständige Analyse als JSON, Notizen, Markierungen, manuelle Kapitelzuordnung |
| `pages` | Text pro physischer Seite, gedruckte Seitenzahl und ihre Quelle, Qualität |
| `pages_fts`, `studies_fts` | FTS5-Volltextindex (PDF-Text bzw. Analyse, Metadaten, Notizen) |
| `evidence` | Belegtabelle: Aussage, Studie, PDF-Seite, gedruckte Seite, Originalzitat, Status, Quelle, Ergebnis der Zitatprüfung |
| `ai_outputs` | Gespeicherte KI-Synthesen (Vergleich, Theorie, Methodik, Lücken) mit verwendeten Studien und Modell |
| `user_notes` | Kapitel- und Methodiknotizen |
| `settings` | z. B. angepasster Kontext der Masterarbeit |

Status einer Studie: `extracted` → `queued` → `analyzing` → `analyzed`, außerdem `no_api` (kein Schlüssel), `needs_ocr` und `error`.

---

## 6. Konfiguration (`.env`)

| Variable | Standard | Bedeutung |
|---|---|---|
| `HUB_PROVIDER` | `anthropic` | KI-Anbieter: `anthropic` (Claude) oder `openai` (ChatGPT/GPT) |
| `ANTHROPIC_API_KEY` | – | Claude-API-Schlüssel (console.anthropic.com). Bleibt im Backend und erscheint nie im Browser |
| `OPENAI_API_KEY` | – | OpenAI-API-Schlüssel (platform.openai.com), nur bei `HUB_PROVIDER=openai` |
| `HUB_OPENAI_MODEL` | `gpt-5.5` | OpenAI-Modell; Namen gemäß platform.openai.com |
| `HUB_OPENAI_EFFORT` | `medium` | Denktiefe der OpenAI-Reasoning-Modelle (`low`/`medium`/`high`); wird automatisch weggelassen, wenn das Modell sie nicht unterstützt |
| `HUB_CLAUDE_MODEL` | `claude-opus-5-5` | Modell |
| `HUB_CLAUDE_EFFORT` | `high` | Analysetiefe: `low` bis `max` (höher = gründlicher und teurer) |
| `HUB_REFUSAL_FALLBACK` | `true` | Server-seitiger Fallback, falls ein Sicherheitsfilter eine Anfrage ablehnt |
| `ANALYSIS_WORKERS` | `2` | Parallele Analysen |
| `MAX_TEXT_CHARS` | `600000` | Max. Textmenge pro Studie. Darüber hinausgehende Seiten werden ausgelassen und **ausdrücklich vermerkt** |
| `MAX_UPLOAD_MB` | `80` | Max. Dateigröße |
| `DATA_DIR` | `./data` | Speicherort für Daten |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Nur lokal erreichbar |

**Hinweis zu Abos:** Weder ein Claude.ai- noch ein ChatGPT-Abo (Plus/Pro) enthält API-Zugang. Für beide Anbieter braucht man einen separaten API-Schlüssel mit eigenem Guthaben.

**Kosten:** Für einen typischen Artikel mit 10–25 Seiten sind grob einige zehntausend Token pro Analyse zu erwarten, also Kosten im Bereich von Cent bis unter einem Dollar pro Studie. Die tatsächlichen Werte hängen von Länge und Effort ab und stehen pro Studie in der Datenbank (`analysis_usage`). „Alle neu analysieren“ fragt vorher nach.

---

## 7. Datenschutz

- An die gewählte KI-API (Anthropic oder OpenAI) geht **nur** der extrahierte Text der importierten wissenschaftlichen PDFs bzw. daraus abgeleitete Analysen (für Synthesen).
- Die App hat keine Funktion für Spieler- oder Vereinsdaten. Bitte keine internen FCZ-Dokumente importieren (WIMU- oder ForceDecks-Exporte, Spielerlisten, Berichte).
- Alle Daten liegen lokal in `data/`. Der Server ist standardmäßig nur über `127.0.0.1` erreichbar.
- `.env` und `data/` stehen in `.gitignore`.

---

## 8. Bekannte Grenzen und Fehlerfälle

| Fall | Verhalten / Hinweis |
|---|---|
| **Eingescannte PDFs** | Werden als `needs_ocr` erkannt und nicht analysiert. Lösung: `ocrmypdf eingabe.pdf ausgabe.pdf` (Tesseract), danach die OCR-Version importieren. Einzelne Bildseiten in sonst lesbaren PDFs werden gemeldet und von der Analyse ausgenommen |
| **Tabellen und Abbildungen** | Werte aus Tabellen werden als Text extrahiert, oft ohne Struktur. Werte aus Abbildungen kann die App nicht lesen. Die KI ist angewiesen, solche Angaben als *unsicher* zu markieren. Zahlen aus Tabellen immer im PDF prüfen |
| **Zitat „nicht gefunden“** | Häufige Ursachen: Zitat über zwei Spalten oder Seiten, Sonderzeichen (±, η²), Fußnoten, leichte Umformulierung durch die KI. Der Status ist dann *unsicher*, die Seite ist trotzdem verlinkt |
| **Markierung im PDF fehlt** | Die Markierung nutzt die PyMuPDF-Suche in Abschnitten von 7 Wörtern. Bei mehrspaltigem Satz oder Ligaturen kann sie unvollständig sein. Die Seitennavigation funktioniert trotzdem |
| **Gedruckte Seitenzahlen** | Ohne PDF-Seitenlabels werden sie aus Kopf- und Fußzeilen abgeleitet (konsistenter Versatz über mindestens 40 % der Seiten). Bei Preprints oder Supplements ggf. nicht vorhanden. Maßgeblich ist immer die physische PDF-Seite |
| **Bibliografische Metadaten** | Werden aus dem Dokument extrahiert, nicht aus Datenbanken wie Crossref. BibTeX und RIS vor der Verwendung prüfen |
| **Sehr lange Dokumente** (Bücher, Dissertationen) | Text über `MAX_TEXT_CHARS` wird nicht analysiert. Die fehlenden Seiten werden angezeigt |
| **Variablen-Normalisierung** | Die Zuordnung von GPS- und CMJ-Variablen zu Standardkategorien (z. B. „FT:CT“, „HSR“) ist schlüsselwortbasiert. Ungewöhnliche Bezeichnungen landen unter ihrem Originalnamen |
| **Lückenanalyse** | Zeigt nur Lücken *innerhalb der importierten Literatur*. Für eine belastbare Aussage über den Forschungsstand ist eine systematische Recherche nötig |
| **KI-Fehler** | Ungültiger Schlüssel (401), Rate-Limit (429), Netzwerk: Die Studie erhält den Status `error` mit Meldung und kann später erneut analysiert werden. Wird der Server während einer Analyse beendet, wird der Status beim nächsten Start zurückgesetzt |
| **Mehrere Nutzer** | Ausgelegt für eine Person an einem Rechner. Kein Login |

---

## 9. Tests

```bash
python backend/tests/smoke_test.py
```

Der Rauchtest prüft ohne API-Schlüssel mit einem synthetischen PDF: Import, Dubletten, Ablehnung von Nicht-PDFs, Erkennung von Scan-Seiten, gedruckte Seitenzahlen, Zitatprüfung (Abwertung eines erfundenen Zitats), Relevanzberechnung, Volltextsuche und alle Exporte.

---

## 10. REST-API (Auszug)

| Methode | Pfad | Zweck |
|---|---|---|
| `POST` | `/api/studies/upload?analyze=true` | PDFs hochladen (multipart, Feld `files`) |
| `GET` | `/api/studies`, `/api/studies/{id}` | Liste bzw. Detail inkl. Analyse |
| `POST` | `/api/studies/{id}/analyze` | (Erneute) KI-Analyse |
| `POST` | `/api/studies/analyze-pending` | Alle ausstehenden analysieren |
| `PATCH` | `/api/studies/{id}` | Notizen, Markierungen, Kapitelzuordnung |
| `GET` | `/api/studies/{id}/pdf` · `/search?q=` · `/highlight?page=&q=` | PDF, Suche im PDF, Markierungskoordinaten |
| `GET` | `/api/search?q=` | Volltextsuche (FTS5) |
| `GET` | `/api/dashboard`, `/api/matrix`, `/api/gaps` | Kennzahlen, Matrix, Lückenzählungen |
| `POST` | `/api/compare`, `/api/compare/ai` | Vergleichstabelle, KI-Vergleich |
| `GET/POST` | `/api/theory/{kapitel}`, `/api/methods/{thema}` (+ `/ai`) | Assistenten |
| `GET` | `/api/export/{csv,xlsx,json,docx,bibtex,ris}` | Exporte |
| `POST` | `/api/backup`, `/api/restore` | Backup und Wiederherstellung |

Interaktive API-Dokumentation: http://localhost:8000/docs
