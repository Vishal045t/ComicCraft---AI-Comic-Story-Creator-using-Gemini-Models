import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402


@pytest.fixture(autouse=True)
def offline_env(monkeypatch):
    """Tests never touch the network or real API keys."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    monkeypatch.setattr(config, "HF_API_KEY", "")
    monkeypatch.setattr(config, "ENABLE_FREE_IMAGE_FALLBACK", False)


@pytest.fixture(autouse=True)
def cleanup_generated():
    before = {p for d in (config.PANELS_DIR, config.EXPORTS_DIR, config.COMICS_DIR) for p in d.glob("*") if p.name != ".gitkeep"}
    yield
    for d in (config.PANELS_DIR, config.EXPORTS_DIR, config.COMICS_DIR):
        for p in d.glob("*"):
            if p.name != ".gitkeep" and p not in before:
                p.unlink()
