"""Small shared helpers."""
import json
import re
from typing import Any


def extract_json(text: str) -> Any:
    """Parse JSON from a model answer even if it is wrapped in markdown fences or extra prose."""
    if text is None:
        raise ValueError("empty response")
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Fall back to the outermost {...} or [...] block.
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start, end = cleaned.find(open_ch), cleaned.rfind(close_ch)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("response did not contain valid JSON")


def clean_str(value: Any, limit: int = 600) -> str:
    """Single-line-safe string: no markdown asterisks, collapsed spaces, bounded length."""
    if value is None:
        return ""
    text = str(value).replace("**", "").replace("*", "")
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text[:limit]
