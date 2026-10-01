"""The full generation pipeline: outline -> story -> images -> layout -> PDF -> saved record."""
import threading
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable, Dict, Optional

from app import config
from app.exporters import save_pdf
from app.gemini_flash import generate_outline
from app.gemini_pro import generate_story
from app.image_generator import generate_image_with_source
from app.layout_builder import build_comic_layout
from app.schemas import ComicRequest
from app.storage import new_id, save_comic

Progress = Callable[[int, str], None]


def build_full_prompt(req: ComicRequest) -> str:
    return (f"{req.prompt}\n"
            f"The main character is {req.character_name}. The setting is: {req.setting}. "
            f"The tone is {req.tone}. The art style is {req.style}.")


def build_image_prompt(req: ComicRequest, outline: Dict, panel: Dict) -> str:
    """Every panel prompt repeats the same style + character description so the look stays consistent."""
    parts = [
        config.STYLE_PROMPTS.get(req.style, req.style),
        panel["image_prompt"],
        f"main character: {outline.get('character_description') or req.character_name}",
        f"setting: {req.setting}",
        f"mood: {req.tone}",
        "the same character design in every panel, single main character, full color",
    ]
    return ". ".join(p.strip().rstrip(".") for p in parts if p)


def run_pipeline(req: ComicRequest, progress: Optional[Progress] = None) -> Dict:
    report = progress or (lambda pct, msg: None)
    comic_id = new_id()
    warnings = []

    report(5, "Planning your 5 panels…")
    outline = generate_outline(build_full_prompt(req), req.character_name, req.setting, req.tone, req.style, idea=req.prompt)

    report(20, "Writing the story and dialogue…")
    story = generate_story(outline, req.character_name, req.tone)
    if outline["source"] == "offline":
        warnings.append("Gemini was unavailable, so a simple built-in story was used. Check GEMINI_API_KEY and your internet connection.")

    report(30, "Drawing panel 1 of 5…")
    seed = zlib.crc32(comic_id.encode()) % (2 ** 31)
    done = {"count": 0}
    lock = threading.Lock()
    total = len(outline["panels"])

    def draw(panel: Dict) -> Dict:
        path, source = generate_image_with_source(
            build_image_prompt(req, outline, panel),
            filename=f"{comic_id}_{panel['panel']}.png", seed=seed, label=panel["title"])
        with lock:
            done["count"] += 1
            finished = done["count"]
        report(30 + int(60 * finished / total), f"Drew panel {finished} of {total}…")
        return {"path": path, "source": source}

    with ThreadPoolExecutor(max_workers=config.IMAGE_WORKERS) as pool:
        images = list(pool.map(draw, outline["panels"]))

    if any(img["source"] == "placeholder" for img in images):
        warnings.append("Some illustrations could not be generated and show a placeholder. Check HF_API_KEY / quota and try again.")

    report(93, "Laying out the pages…")
    layout = build_comic_layout(images, story, outline)
    meta = {"title": outline["title"], "character_name": req.character_name, "setting": req.setting,
            "tone": req.tone, "style": req.style, "prompt": req.prompt}

    report(96, "Exporting the PDF…")
    pdf_path = save_pdf(layout, meta, comic_id)

    record = {"id": comic_id, "created": datetime.now(timezone.utc).isoformat(), "meta": meta,
              "layout": layout, "pdf_path": pdf_path, "warnings": warnings}
    save_comic(record)
    report(100, "Done!")
    return record
