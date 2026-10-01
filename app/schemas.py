"""Request validation shared by the HTML form, the JSON API and the background-job endpoint."""
from pydantic import BaseModel, Field, field_validator

from app import config


def _normalise(value: str) -> str:
    return " ".join((value or "").strip().lower().replace("_", " ").split())


class ComicRequest(BaseModel):
    prompt: str = Field(..., min_length=5, max_length=600)
    character_name: str = Field(..., min_length=1, max_length=40)
    setting: str = "forest"
    tone: str = "dramatic"
    style: str = "comic book"

    @field_validator("prompt", "character_name", mode="before")
    @classmethod
    def _strip(cls, v):
        return " ".join(str(v or "").split())

    @field_validator("setting", "tone", "style", mode="before")
    @classmethod
    def _lower(cls, v):
        return _normalise(str(v))

    @field_validator("setting")
    @classmethod
    def _check_setting(cls, v):
        if v not in config.SETTING_KEYS:
            raise ValueError(f"setting must be one of {config.SETTING_KEYS}")
        return v

    @field_validator("tone")
    @classmethod
    def _check_tone(cls, v):
        v = v.replace(" ", "-") if v.replace(" ", "-") in config.TONE_KEYS else v
        if v not in config.TONE_KEYS:
            raise ValueError(f"tone must be one of {config.TONE_KEYS}")
        return v

    @field_validator("style")
    @classmethod
    def _check_style(cls, v):
        if v not in config.STYLE_KEYS:
            raise ValueError(f"style must be one of {config.STYLE_KEYS}")
        return v
