"""Hintergrundverarbeitung der KI-Analysen (Thread-Pool, Status in der DB)."""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from . import config, db, services

log = logging.getLogger("research_hub.jobs")

_executor = ThreadPoolExecutor(max_workers=max(1, config.ANALYSIS_WORKERS), thread_name_prefix="analysis")
_active: set[int] = set()
_lock = threading.Lock()


def _run(study_id: int) -> None:
    try:
        services.run_analysis(study_id)
    except Exception:  # noqa: BLE001
        log.exception("Unerwarteter Fehler in Analyse %s", study_id)
    finally:
        with _lock:
            _active.discard(study_id)
        db.close_thread_conn()


def enqueue(study_id: int) -> bool:
    """Stellt eine Studie zur Analyse ein. False, falls bereits aktiv."""
    with _lock:
        if study_id in _active:
            return False
        _active.add(study_id)
    with db.tx() as c:
        c.execute("UPDATE studies SET status='queued', status_message='In Warteschlange für KI-Analyse' WHERE id=?",
                  (study_id,))
    _executor.submit(_run, study_id)
    return True


def recover_interrupted() -> None:
    """Nach Neustart: hängengebliebene Analysen zurücksetzen."""
    with db.tx() as c:
        c.execute("UPDATE studies SET status=CASE WHEN analysis_json IS NOT NULL THEN 'analyzed' ELSE 'extracted' END, "
                  "status_message='Analyse wurde durch Neustart unterbrochen – bitte erneut starten.' "
                  "WHERE status IN ('queued','analyzing')")


def active() -> list[int]:
    with _lock:
        return sorted(_active)
