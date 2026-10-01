"""Central configuration: paths, API keys, model lists and the allowed form options."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _csv(name: str, default: str) -> list:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# ---- Paths -----------------------------------------------------------------
STATIC_DIR = BASE_DIR / "static"
PANELS_DIR = STATIC_DIR / "panels"
EXPORTS_DIR = STATIC_DIR / "exports"
FONTS_DIR = STATIC_DIR / "fonts"
TEMPLATES_DIR = BASE_DIR / "templates"
COMICS_DIR = BASE_DIR / "storage" / "comics"

# ---- API keys / models -------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
HF_API_KEY = os.getenv("HF_API_KEY", "").strip()

GEMINI_FLASH_MODELS = _csv(
    "GEMINI_FLASH_MODELS",
    "gemini-3.5-flash,gemini-flash-latest,gemini-3-flash-preview,gemini-2.5-flash",
)
GEMINI_PRO_MODELS = _csv(
    "GEMINI_PRO_MODELS",
    "gemini-3.1-pro-preview,gemini-pro-latest,gemini-2.5-pro",
)
HF_IMAGE_MODELS = _csv(
    "HF_IMAGE_MODELS",
    "black-forest-labs/FLUX.1-schnell,stabilityai/stable-diffusion-xl-base-1.0",
)
ENABLE_FREE_IMAGE_FALLBACK = _bool("ENABLE_FREE_IMAGE_FALLBACK", True)
IMAGE_WORKERS = max(1, min(4, int(os.getenv("IMAGE_WORKERS", "2") or 2)))
PANEL_COUNT = 5

# ---- Form options (single source of truth for the UI *and* the validation) ----
SETTINGS = [
    ("forest", "🌲", "Forest"),
    ("school", "🏫", "School"),
    ("space", "🚀", "Space"),
    ("city", "🌆", "City"),
    ("castle", "🏰", "Castle"),
    ("ocean", "🌊", "Ocean"),
]
TONES = [
    ("dramatic", "Dramatic"),
    ("light-hearted", "Light-hearted"),
    ("funny", "Funny"),
    ("poetic", "Poetic"),
    ("mysterious", "Mysterious"),
]
STYLES = [
    ("anime", "Anime"),
    ("comic book", "Comic book"),
    ("pixel art", "Pixel art"),
    ("realistic", "Realistic"),
    ("watercolor", "Watercolor"),
]
STYLE_PROMPTS = {
    "anime": "anime illustration, vibrant colors, clean line art, expressive eyes",
    "comic book": "classic comic book art, bold ink outlines, halftone shading, dynamic composition",
    "pixel art": "16-bit pixel art, retro video game style, crisp pixels",
    "realistic": "photorealistic, cinematic lighting, highly detailed, natural textures",
    "watercolor": "soft watercolor painting, gentle gradients, paper texture, storybook illustration",
}
SAMPLE_IDEAS = [
    "A brave fox exploring an enchanted forest",
    "A tiny robot learns to paint sunsets",
    "Two astronauts find a planet made of cheese",
    "A lighthouse keeper hears singing from the deep",
]

SETTING_KEYS = [s[0] for s in SETTINGS]
TONE_KEYS = [t[0] for t in TONES]
STYLE_KEYS = [s[0] for s in STYLES]


def ensure_dirs() -> None:
    for folder in (PANELS_DIR, EXPORTS_DIR, COMICS_DIR):
        folder.mkdir(parents=True, exist_ok=True)
