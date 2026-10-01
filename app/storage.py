"""Tiny persistence layer: comics are saved as JSON files, background jobs are kept in memory."""
import json
import re
import threading
import time
import uuid
from typing import Dict, Optional

from app import config

_ID_RE = re.compile(r"^[a-f0-9]{12}$")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def is_valid_id(value: str) -> bool:
    return bool(value and _ID_RE.match(value))


def save_comic(record: Dict) -> None:
    config.ensure_dirs()
    path = config.COMICS_DIR / f"{record['id']}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def load_comic(comic_id: str) -> Optional[Dict]:
    if not is_valid_id(comic_id):
        return None
    path = config.COMICS_DIR / f"{comic_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


class JobStore:
    """Thread-safe in-memory job table used for progress polling."""

    def __init__(self):
        self._jobs: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    def create(self) -> str:
        job_id = new_id()
        with self._lock:
            self._prune()
            self._jobs[job_id] = {"id": job_id, "status": "running", "progress": 0, "message": "Starting…",
                                  "comic_id": None, "error": None, "created": time.time()}
        return job_id

    def update(self, job_id: str, **fields) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(fields)

    def get(self, job_id: str) -> Optional[Dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def _prune(self) -> None:
        cutoff = time.time() - 3600
        for key in [k for k, v in self._jobs.items() if v["created"] < cutoff]:
            del self._jobs[key]


jobs = JobStore()
