"""Rauchtest ohne API-Schlüssel: Import, Extraktion, OCR-Erkennung, Seitenzahlen,
Dubletten, Zitatprüfung, Exporte. Aufruf (im Projektordner): python backend/tests/smoke_test.py"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
tmp = tempfile.mkdtemp(prefix="rh_smoke_")
os.environ["DATA_DIR"] = tmp
os.environ["ANTHROPIC_API_KEY"] = ""
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "sample"))

from app import config, db, exports, services  # noqa: E402
from make_test_pdf import make  # noqa: E402

config.ANTHROPIC_API_KEY = ""
db.init_db()
pdf = Path(tmp) / "test.pdf"
make(str(pdf))
data = pdf.read_bytes()

r = services.import_pdf("test.pdf", data)
assert r["result"] == "imported", r
tq = r["text_quality"]
assert tq["overall"] == "partial" and tq["scanned_pages"] == [4], tq
assert services.import_pdf("kopie.pdf", data)["result"] == "duplicate"
assert services.import_pdf("x.pdf", b"kein pdf")["result"] == "error"
pages = services.get_pages(r["study_id"])
assert [p["page_label"] for p in pages] == ["101", "102", "103", "104"], pages

analysis = json.loads((ROOT / "sample" / "beispiel_analyse.json").read_text(encoding="utf-8"))["analysis"]
for k in ("verification", "meta"):
    analysis.pop(k, None)
analysis["design"]["research_question"]["quote"] = "Dieses Zitat steht nicht im Dokument und muss abgewertet werden"
analysis["design"]["research_question"]["status"] = "verified"
services.save_analysis(r["study_id"], analysis, {"model": "smoke-test"})
row = services.get_study_row(r["study_id"])
a = json.loads(row["analysis_json"])
assert a["design"]["research_question"]["status"] == "uncertain"
assert a["design"]["research_question"]["check"]["quote_check"] == "not_found"
assert a["design"]["study_type"]["check"]["quote_check"] == "exact"
assert a["design"]["study_type"]["page_label"] == "102"
assert row["relevance_score"] == 85.0, row["relevance_score"]
assert services.search("force plates")["studies"]
for fn in (exports.to_csv, exports.to_xlsx, exports.to_json, exports.to_docx, exports.to_bibtex, exports.to_ris):
    assert len(fn()) > 100, fn.__name__
print("Rauchtest erfolgreich:", row["status_message"])
