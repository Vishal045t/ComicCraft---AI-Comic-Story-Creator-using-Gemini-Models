"""Gemini Pro: narration and dialogue for each panel (structured JSON, matched to panels by number)."""
import json
from typing import Dict, List

from app import config
from app.fallbacks import offline_story
from app.gemini_client import GeminiUnavailable, generate_text
from app.utils import clean_str, extract_json


def _build_prompt(outline: Dict, character_name: str, tone: str) -> str:
    panels = "\n".join(f"Panel {p['panel']} - {p['title']}: {p['scene_description']}" for p in outline["panels"])
    return f"""You are a comic book writer. Write the text for a {config.PANEL_COUNT}-panel comic titled "{outline['title']}".
Main character: {character_name}. Tone: {tone}.

Panel plan:
{panels}

Rules:
- For every panel write: a short "caption" (max 12 words), one "narration" paragraph (1-2 sentences), and 1-2 lines of "dialogue".
- Dialogue lines are short (max 15 words) and spoken by the characters in the scene.
- Keep it cohesive from panel 1 to panel {config.PANEL_COUNT}, in a {tone} tone, suitable for all ages.

Respond with ONLY valid JSON (no markdown) in exactly this shape:
{{"panels": [{{"panel": 1, "caption": "...", "narration": "...", "dialogue": [{{"speaker": "Name", "text": "..."}}]}}]}}"""


def normalize_story(data, outline: Dict) -> List[Dict]:
    if isinstance(data, dict):
        data = data.get("panels")
    if not isinstance(data, list):
        raise ValueError("story is not a list")
    by_number = {}
    for position, raw in enumerate(data, start=1):
        if not isinstance(raw, dict):
            continue
        try:
            number = int(raw.get("panel", position))
        except (TypeError, ValueError):
            number = position
        dialogue = []
        for line in raw.get("dialogue") or []:
            if isinstance(line, dict) and clean_str(line.get("text")):
                dialogue.append({"speaker": clean_str(line.get("speaker"), 40) or "Narrator", "text": clean_str(line.get("text"), 200)})
            elif isinstance(line, str) and line.strip():
                dialogue.append({"speaker": "", "text": clean_str(line, 200)})
        by_number[number] = {
            "panel": number,
            "caption": clean_str(raw.get("caption"), 120),
            "narration": clean_str(raw.get("narration"), 500),
            "dialogue": dialogue[:3],
        }
    story = []
    for panel in outline["panels"]:
        item = by_number.get(panel["panel"])
        if not item or not (item["narration"] or item["caption"] or item["dialogue"]):
            raise ValueError(f"story is missing panel {panel['panel']}")
        story.append(item)
    return story


def generate_story(outline: Dict, character_name: str = "Hero", tone: str = "light-hearted") -> List[Dict]:
    """Return a list of 5 dicts (panel, caption, narration, dialogue). Falls back to offline text."""
    last_error = None
    if outline.get("source") != "offline":
        for _ in range(2):
            try:
                text = generate_text(_build_prompt(outline, character_name, tone), role="pro", json_mode=True)
                return normalize_story(extract_json(text), outline)
            except GeminiUnavailable as exc:
                last_error = exc
                break
            except ValueError as exc:
                last_error = exc
                print(f"[story] invalid response, retrying: {exc}")
        print(f"[story] using offline story ({last_error})")
    story_outline = dict(outline, character_name=character_name)
    return offline_story(story_outline, tone)
