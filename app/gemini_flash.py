"""Gemini Flash: fast, structured 5-panel outline."""
from typing import Dict

from app import config
from app.fallbacks import offline_outline
from app.gemini_client import GeminiUnavailable, generate_text
from app.utils import clean_str, extract_json

REQUIRED = ("title", "scene_description", "image_prompt")


def _build_prompt(user_prompt: str) -> str:
    n = config.PANEL_COUNT
    return f"""You are a professional comic book planner.

Plan a comic with EXACTLY {n} panels for this brief:
{user_prompt}

Rules:
- The story must have a clear beginning, middle and end across the {n} panels.
- The same single main character appears in every panel.
- "character_description" is one sentence describing the character's fixed appearance
  (species/age, colors, outfit, distinctive features) so every illustration looks the same.
- "image_prompt" describes ONLY what to draw (subject, action, camera angle, lighting, background).
  Do not mention text, speech bubbles or captions in image prompts.
- Keep content friendly and suitable for all ages.

Respond with ONLY valid JSON (no markdown, no commentary) in exactly this shape:
{{
  "title": "Short comic title",
  "character_description": "Fixed look of the main character",
  "panels": [
    {{"panel": 1, "title": "Panel title", "scene_description": "What happens", "image_prompt": "What to draw"}}
  ]
}}"""


def normalize_outline(data, character_name: str = "") -> Dict:
    """Validate/repair the model output. Raises ValueError if it cannot be used."""
    if isinstance(data, list):  # older prompt format: a bare list of panels
        data = {"panels": data}
    if not isinstance(data, dict):
        raise ValueError("outline is not a JSON object")
    panels_raw = data.get("panels")
    if not isinstance(panels_raw, list) or len(panels_raw) < config.PANEL_COUNT:
        raise ValueError(f"expected {config.PANEL_COUNT} panels, got {len(panels_raw) if isinstance(panels_raw, list) else 0}")

    panels = []
    for i, raw in enumerate(panels_raw[: config.PANEL_COUNT], start=1):
        if not isinstance(raw, dict):
            raise ValueError("panel is not an object")
        scene = clean_str(raw.get("scene_description"), 500)
        image_prompt = clean_str(raw.get("image_prompt"), 500) or scene
        if not scene and not image_prompt:
            raise ValueError(f"panel {i} is empty")
        panels.append({
            "panel": i,
            "title": clean_str(raw.get("title"), 80) or f"Panel {i}",
            "scene_description": scene or image_prompt,
            "image_prompt": image_prompt,
        })
    return {
        "title": clean_str(data.get("title"), 80) or (f"The Adventures of {character_name}" if character_name else "My Comic"),
        "character_description": clean_str(data.get("character_description"), 300),
        "panels": panels,
    }


def generate_outline(user_prompt: str, character_name: str = "Hero", setting: str = "forest",
                     tone: str = "light-hearted", style: str = "comic book", idea: str = "") -> Dict:
    """Return {'title','character_description','panels':[5 dicts],'source':'gemini'|'offline'}."""
    last_error = None
    for _ in range(2):  # one retry if the JSON comes back malformed
        try:
            text = generate_text(_build_prompt(user_prompt), role="flash", json_mode=True)
            outline = normalize_outline(extract_json(text), character_name)
            outline["source"] = "gemini"
            return outline
        except GeminiUnavailable as exc:
            last_error = exc
            break
        except ValueError as exc:
            last_error = exc
            print(f"[outline] invalid response, retrying: {exc}")
    print(f"[outline] using offline outline ({last_error})")
    outline = offline_outline(idea or user_prompt, character_name, setting, tone, style)
    outline["source"] = "offline"
    return outline
