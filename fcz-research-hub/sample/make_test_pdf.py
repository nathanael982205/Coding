"""Erzeugt ein synthetisches Test-PDF (3 Textseiten mit Seitenzahlen 101–103 + 1 Bildseite ohne Text).

Dient nur zum Testen der Pipeline (Textextraktion, OCR-Erkennung, Seitenzahlen, Zitatprüfung).
Aufruf: python sample/make_test_pdf.py [ausgabe.pdf]
"""
import sys

import pymupdf

PARAS = [
    "Neuromuscular fatigue after match play in professional soccer players. Test Author, Second Author. "
    "Journal of Test Science 2021. doi:10.1234/jts.2021.001",
    "Methods. Twenty professional soccer players participated. External load was monitored using a 10 Hz GPS "
    "system (WIMU PRO). High-speed running was defined as distance covered above 19.8 km/h. Countermovement jump "
    "height was assessed on dual force plates (VALD ForceDecks) at MD-1, MD+1 and MD+2.",
    "Results. CMJ jump height was reduced at MD+1 compared with baseline (ES = -0.65). Linear mixed models were "
    "used to account for repeated measures within players.",
]


def make(out: str) -> None:
    doc = pymupdf.open()
    for i, t in enumerate(PARAS):
        p = doc.new_page()
        p.insert_textbox(pymupdf.Rect(50, 80, 550, 700), t, fontsize=11)
        p.insert_text((300, 820), str(101 + i), fontsize=9)
    p = doc.new_page()  # "eingescannte" Seite: nur Bild, kein Text
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 200), 0)
    pix.clear_with(200)
    p.insert_image(pymupdf.Rect(50, 50, 500, 500), pixmap=pix)
    doc.save(out)


if __name__ == "__main__":
    make(sys.argv[1] if len(sys.argv) > 1 else "test_studie.pdf")
