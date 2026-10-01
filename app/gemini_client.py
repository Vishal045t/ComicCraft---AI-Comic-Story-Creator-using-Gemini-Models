"""Thin, defensive wrapper around the Google Gemini API.

* Discovers which models your key can actually use (so a wrong/retired model name never breaks the app).
* Retries temporary errors (429/503) with back-off and falls through to the next model.
* Raises GeminiUnavailable when nothing works, so the pipeline can switch to its offline fallback.
"""
import re
import time
from typing import List, Optional

from app import config


class GeminiUnavailable(RuntimeError):
    """Raised when Gemini cannot be used (no key, quota exhausted, every model failed)."""


_client = None
_discovered: Optional[List[str]] = None
_SKIP_WORDS = ("image", "tts", "audio", "live", "native", "embedding", "robotics", "computer-use", "vision", "omni")


def _get_client():
    global _client
    if not config.GEMINI_API_KEY:
        raise GeminiUnavailable("GEMINI_API_KEY is not set")
    if _client is None:
        from google import genai  # imported lazily so the app still starts without the package configured

        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _discover_models() -> List[str]:
    """Names of text-capable models the key can call (cached). Empty list if listing fails."""
    global _discovered
    if _discovered is not None:
        return _discovered
    names = []
    try:
        for model in _get_client().models.list():
            name = (getattr(model, "name", "") or "").replace("models/", "")
            actions = getattr(model, "supported_actions", None) or []
            if name and (not actions or "generateContent" in actions):
                names.append(name)
    except Exception as exc:  # listing is a nicety, never a requirement
        print(f"[gemini] could not list models ({exc}); using configured names")
    _discovered = names
    return names


def _version_key(name: str):
    return tuple(int(n) for n in re.findall(r"\d+", name))


def candidate_models(role: str) -> List[str]:
    configured = config.GEMINI_PRO_MODELS if role == "pro" else config.GEMINI_FLASH_MODELS
    fallback_family = "pro" if role == "pro" else "flash"
    available = _discover_models()

    if not available:
        ordered = list(configured)
    else:
        ordered = [m for m in configured if m in available]
        extras = [
            m for m in available
            if fallback_family in m and not any(w in m for w in _SKIP_WORDS) and m not in ordered
        ]
        extras.sort(key=lambda m: ("lite" in m, tuple(-n for n in _version_key(m))))
        ordered += extras
    # Pro role may always fall back to a flash model so story generation still works.
    if role == "pro":
        for m in candidate_models("flash"):
            if m not in ordered:
                ordered.append(m)
    return ordered


def _is_retryable(msg: str) -> bool:
    msg = msg.lower()
    return any(k in msg for k in ("429", "503", "500", "unavailable", "overloaded", "timeout", "deadline", "resource_exhausted"))


def generate_text(prompt: str, role: str = "flash", json_mode: bool = False, retries: int = 2) -> str:
    """Return the model's text answer or raise GeminiUnavailable."""
    client = _get_client()
    models = candidate_models(role)
    if not models:
        raise GeminiUnavailable("no Gemini model is available for this API key")

    from google.genai import types

    last_error = None
    for model_name in models:
        for attempt in range(retries + 1):
            try:
                cfg = types.GenerateContentConfig(
                    temperature=0.9,
                    response_mime_type="application/json" if json_mode else None,
                )
                response = client.models.generate_content(model=model_name, contents=prompt, config=cfg)
                text = (getattr(response, "text", None) or "").strip()
                if not text:
                    raise ValueError("empty response (possibly blocked by safety filters)")
                return text
            except Exception as exc:
                last_error = exc
                msg = str(exc)
                print(f"[gemini] {model_name} attempt {attempt + 1} failed: {msg[:200]}")
                if _is_retryable(msg) and attempt < retries:
                    time.sleep(2 * (attempt + 1))
                    continue
                break  # try the next model
    raise GeminiUnavailable(f"all Gemini models failed: {last_error}")
