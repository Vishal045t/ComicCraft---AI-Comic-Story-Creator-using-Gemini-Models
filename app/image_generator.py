"""Panel image generation.

Order of attempts: Hugging Face models (needs HF_API_KEY) -> free keyless fallback -> drawn placeholder.
A panel image is ALWAYS produced, so a comic never fails because an image service is down.
"""
import io
import textwrap
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from app import config

IMAGE_SIZE = 768
_NO_RETRY = ("402", "quota", "credit", "exceeded", "payment", "401", "403", "unauthorized", "forbidden", "invalid")
_hf_client = None


def _save(image: Image.Image, path: Path) -> None:
    image = image.convert("RGB")
    image.thumbnail((IMAGE_SIZE, IMAGE_SIZE))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)


def _font(size: int):
    for candidate in (config.FONTS_DIR / "DejaVuSans-Bold.ttf", config.FONTS_DIR / "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(str(candidate), size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_placeholder(path: Path, label: str, note: str = "Illustration unavailable") -> None:
    img = Image.new("RGB", (IMAGE_SIZE, IMAGE_SIZE), (30, 33, 56))
    draw = ImageDraw.Draw(img)
    for y in range(IMAGE_SIZE):  # simple vertical gradient
        shade = int(30 + 60 * y / IMAGE_SIZE)
        draw.line([(0, y), (IMAGE_SIZE, y)], fill=(shade, 33 + shade // 4, 56 + shade // 2))
    draw.rectangle([24, 24, IMAGE_SIZE - 24, IMAGE_SIZE - 24], outline=(140, 120, 255), width=4)
    draw.text((56, 70), note, fill=(255, 255, 255), font=_font(34))
    wrapped = textwrap.fill(label[:200], 34)
    draw.multiline_text((56, 140), wrapped, fill=(220, 220, 240), font=_font(26), spacing=8)
    _save(img, path)


def _hf():
    global _hf_client
    if _hf_client is None:
        from huggingface_hub import InferenceClient

        _hf_client = InferenceClient(api_key=config.HF_API_KEY)
    return _hf_client


def _from_huggingface(prompt: str, seed: Optional[int], retries: int = 1) -> Optional[Image.Image]:
    if not config.HF_API_KEY:
        return None
    import time

    for model in config.HF_IMAGE_MODELS:
        for attempt in range(retries + 1):
            try:
                try:
                    return _hf().text_to_image(prompt, model=model, seed=seed) if seed is not None else _hf().text_to_image(prompt, model=model)
                except TypeError:  # older huggingface_hub without `seed`
                    return _hf().text_to_image(prompt, model=model)
            except Exception as exc:
                msg = str(exc).lower()
                print(f"[image] {model} attempt {attempt + 1} failed: {str(exc)[:160]}")
                if any(marker in msg for marker in _NO_RETRY):
                    return None  # quota/auth problem: every HF model will fail the same way
                if attempt < retries:
                    time.sleep(4 * (attempt + 1))
    return None


def _from_free_service(prompt: str, seed: Optional[int]) -> Optional[Image.Image]:
    if not config.ENABLE_FREE_IMAGE_FALLBACK:
        return None
    try:
        query = urllib.parse.urlencode({"width": 768, "height": 768, "nologo": "true", "seed": seed or 1})
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt[:700])}?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": "ComicCraft/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
        image = Image.open(io.BytesIO(data))
        image.load()
        return image
    except Exception as exc:
        print(f"[image] free fallback failed: {str(exc)[:160]}")
        return None


def generate_image_with_source(prompt: str, filename: Optional[str] = None, seed: Optional[int] = None,
                               label: str = "") -> Tuple[str, str]:
    """Create the image file. Returns (relative_path like 'static/panels/x.png', source)."""
    config.ensure_dirs()
    filename = filename or f"panel_{uuid.uuid4().hex[:10]}.png"
    path = config.PANELS_DIR / filename
    rel = f"static/panels/{filename}"
    full_prompt = prompt + ", no text, no letters, no speech bubbles, no captions, no watermark"

    image = _from_huggingface(full_prompt, seed)
    if image is not None:
        try:
            _save(image, path)
            return rel, "huggingface"
        except Exception as exc:
            print(f"[image] could not save Hugging Face image: {exc}")
    image = _from_free_service(full_prompt, seed)
    if image is not None:
        try:
            _save(image, path)
            return rel, "free-service"
        except Exception as exc:
            print(f"[image] could not save fallback image: {exc}")
    make_placeholder(path, label or prompt)
    return rel, "placeholder"


def generate_image(prompt: str, filename: Optional[str] = None) -> str:
    """Compatibility helper (used by /test-image): returns only the saved path."""
    return generate_image_with_source(prompt, filename)[0]
