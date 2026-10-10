"""Startet den FCZ Thesis Research Hub lokal: python run.py  ->  http://localhost:8000"""
import sys
import webbrowser
from pathlib import Path
from threading import Timer

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

import uvicorn  # noqa: E402

from app import config  # noqa: E402

if __name__ == "__main__":
    url = f"http://localhost:{config.PORT}"
    print(f"\n  FCZ Thesis Research Hub läuft unter {url}\n  Beenden mit Strg+C\n")
    if "--no-browser" not in sys.argv:
        Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, log_level="info")
