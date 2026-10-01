"""Combine outline + story + images into the structure used by the preview page and the PDF."""
from typing import Dict, List


def build_comic_layout(image_results: List[Dict], story: List[Dict], outline: Dict) -> List[Dict]:
    """image_results: [{'path': 'static/panels/x.png', 'source': 'huggingface'}, ...] in panel order."""
    story_by_panel = {item["panel"]: item for item in story}
    layout = []
    for panel, image in zip(outline["panels"], image_results):
        text = story_by_panel.get(panel["panel"], {})
        dialogue = text.get("dialogue", [])
        combined = [text.get("narration", "")]
        combined += [f"{d['speaker']}: {d['text']}" if d.get("speaker") else d["text"] for d in dialogue]
        layout.append({
            "panel": panel["panel"],
            "title": panel["title"],
            "image_path": image["path"],
            "image_url": "/" + image["path"].lstrip("/"),
            "image_source": image["source"],
            "scene_description": panel["scene_description"],
            "caption": text.get("caption", ""),
            "narration": text.get("narration", ""),
            "dialogue": dialogue,
            "text": "\n".join(line for line in combined if line),
        })
    return layout
