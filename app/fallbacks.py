"""Offline story/outline generator used when Gemini is unavailable (no key, no quota, no internet).

The app therefore always produces a complete comic instead of an error page.
"""
from typing import Dict, List

from app import config

_ACTS = [
    ("The Beginning", "{c} is introduced in the {s}, ready for an adventure. {idea}",
     "wide establishing shot of {c} in the {s}, calm and curious"),
    ("The Journey", "{c} sets out and explores the {s}, discovering that something unusual is going on.",
     "{c} exploring the {s}, sense of wonder, interesting details in the background"),
    ("The Challenge", "A problem blocks the way. {c} must think carefully to find a solution.",
     "{c} facing a big obstacle in the {s}, tense moment, dramatic composition"),
    ("The Turning Point", "{c} tries a clever idea and everything changes in the {s}.",
     "{c} in action in the {s}, dynamic pose, the key moment of the story"),
    ("The Ending", "The danger is over. {c} looks back at the {s}, happy and proud.",
     "{c} smiling in the {s}, warm light, peaceful ending"),
]

_TONE_LINES = {
    "dramatic": ["The air feels heavy with destiny.", "Every step could change everything.", "Courage is the only way forward.",
                 "It all comes down to this moment!", "At last, calm returns."],
    "light-hearted": ["What a lovely day for an adventure!", "Everything looks bright and friendly.", "Hmm, that is a tricky one!",
                      "Aha! I have an idea!", "That was fun! Let's do it again."],
    "funny": ["Today's plan: look heroic, hope nothing explodes.", "Why is nothing ever where I left it?", "Okay, this is NOT in the instructions.",
              "Trust me, I have totally done this before... once.", "Mission accomplished! Snacks for everyone."],
    "poetic": ["Morning whispers softly through the world.", "Each path is a verse waiting to be written.", "Shadows gather, but hope still glows.",
               "A single spark turns the night to gold.", "And so the story rests, like light upon the water."],
    "mysterious": ["Something here is not what it seems.", "Strange signs appear along the way.", "Who, or what, is watching?",
                   "A hidden truth finally reveals itself.", "Some secrets are kept... but not all."],
}


def offline_outline(idea: str, character: str, setting: str, tone: str, style: str) -> Dict:
    idea_sentence = idea.strip().rstrip(".") + "." if idea.strip() else ""
    panels = []
    for i, (title, scene, img) in enumerate(_ACTS, start=1):
        panels.append({
            "panel": i,
            "title": title,
            "scene_description": scene.format(c=character, s=setting, idea=idea_sentence if i == 1 else "").strip(),
            "image_prompt": img.format(c=character, s=setting) + f", inspired by: {idea.strip()[:160]}",
        })
    return {
        "title": (idea.strip().rstrip(".")[:60] or f"The Adventures of {character}").capitalize(),
        "character_description": f"{character}, the main character, with a distinctive and memorable look",
        "panels": panels,
    }


def offline_story(outline: Dict, tone: str) -> List[Dict]:
    lines = _TONE_LINES.get(tone, _TONE_LINES["light-hearted"])
    character = outline.get("character_name") or "Hero"
    story = []
    for panel, line in zip(outline["panels"], lines):
        story.append({
            "panel": panel["panel"],
            "caption": panel["title"],
            "narration": panel["scene_description"],
            "dialogue": [{"speaker": character, "text": line}],
        })
    return story
