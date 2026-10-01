"""PDF export with FPDF2 (cover page + one page per panel)."""
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fpdf import FPDF

from app import config

_REPLACEMENTS = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u00a0": " "}
_FONT_DIRS = [config.FONTS_DIR, Path("/usr/share/fonts/truetype/dejavu"), Path("C:/Windows/Fonts"), Path("/Library/Fonts"), Path("/System/Library/Fonts/Supplemental")]


def _find_font(names) -> Optional[Path]:
    for folder in _FONT_DIRS:
        for name in names:
            candidate = folder / name
            if candidate.exists():
                return candidate
    return None


def clean_text(text: str, unicode_ok: bool) -> str:
    """Make text safe for the PDF font: strip markdown, emoji and over-long unbroken words."""
    text = (text or "").replace("**", "").replace("*", "")
    text = "".join(ch for ch in text if ord(ch) <= 0xFFFF)  # emoji are not in the PDF font
    text = re.sub(r"(\S{40})(?=\S)", r"\1 ", text)  # allow wrapping of very long words
    if not unicode_ok:
        for old, new in _REPLACEMENTS.items():
            text = text.replace(old, new)
        text = text.encode("latin-1", "replace").decode("latin-1")
    return text


class _ComicPDF(FPDF):
    pass


def save_pdf(layout: List[Dict], meta: Optional[Dict] = None, comic_id: Optional[str] = None) -> str:
    """Write the comic to static/exports and return the relative path ('static/exports/comic_x.pdf')."""
    meta = meta or {}
    config.ensure_dirs()
    pdf = _ComicPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)

    regular = _find_font(["DejaVuSans.ttf"])
    bold = _find_font(["DejaVuSans-Bold.ttf"])
    unicode_ok = regular is not None
    if unicode_ok:
        pdf.add_font("Body", "", str(regular))
        pdf.add_font("Body", "B", str(bold or regular))
        family = "Body"
    else:
        family = "Helvetica"

    def txt(value) -> str:
        return clean_text(str(value or ""), unicode_ok)

    # ---- cover ----
    pdf.add_page()
    pdf.set_fill_color(24, 26, 48)
    pdf.rect(0, 0, 210, 297, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_y(85)
    pdf.set_font(family, "B", 28)
    pdf.multi_cell(0, 14, txt(meta.get("title") or "My AI-Generated Comic"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_font(family, "", 13)
    pdf.set_text_color(200, 200, 235)
    for label, key in (("Starring", "character_name"), ("Setting", "setting"), ("Tone", "tone"), ("Art style", "style")):
        value = meta.get(key)
        if value:
            pdf.cell(0, 9, txt(f"{label}: {str(value).title() if key != 'character_name' else value}"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(250)
    pdf.set_font(family, "", 10)
    pdf.set_text_color(150, 150, 190)
    pdf.cell(0, 7, "Created with ComicCraft", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, datetime.now().strftime("%B %d, %Y"), align="C", new_x="LMARGIN", new_y="NEXT")

    # ---- panels ----
    for panel in layout:
        pdf.add_page()
        pdf.set_text_color(20, 20, 40)
        pdf.set_font(family, "B", 16)
        pdf.multi_cell(0, 9, txt(f"Panel {panel['panel']}: {panel.get('title', '')}"), align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        size = 140
        y = pdf.get_y()
        image_path = config.BASE_DIR / panel["image_path"]
        if image_path.exists():
            pdf.image(str(image_path), x=(210 - size) / 2, y=y, w=size, h=size)
            pdf.set_draw_color(20, 20, 40)
            pdf.set_line_width(0.8)
            pdf.rect((210 - size) / 2, y, size, size)
        else:
            pdf.set_font(family, "", 11)
            pdf.cell(0, 10, "Image missing", align="C")
        pdf.set_y(y + size + 6)

        if panel.get("caption"):
            pdf.set_font(family, "B", 11)
            pdf.set_text_color(90, 70, 160)
            pdf.multi_cell(0, 6, txt(panel["caption"]), align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        pdf.set_text_color(20, 20, 40)
        pdf.set_font(family, "", 12)
        if panel.get("narration"):
            pdf.multi_cell(0, 6.5, txt(panel["narration"]), align="L", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        for line in panel.get("dialogue", []):
            speaker = txt(line.get("speaker"))
            pdf.set_font(family, "B", 12)
            pdf.write(6.5, f"{speaker}: " if speaker else "")
            pdf.set_font(family, "", 12)
            pdf.multi_cell(0, 6.5, txt(line.get("text")), align="L", new_x="LMARGIN", new_y="NEXT")

    suffix = comic_id or datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"comic_{suffix}.pdf"
    pdf.output(str(config.EXPORTS_DIR / filename))
    return f"static/exports/{filename}"
