import json
import time

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import config, gemini_flash, gemini_pro
from app.exporters import clean_text
from app.main import app
from app.pipeline import run_pipeline
from app.schemas import ComicRequest
from app.utils import extract_json

client = TestClient(app)
FORM = {"prompt": "A brave fox explores an enchanted forest", "character_name": "Finn",
        "setting": "forest", "tone": "funny", "style": "anime"}


def good_outline_json():
    return json.dumps({"title": "Finn & the Forest", "character_description": "a red fox with a blue scarf",
                       "panels": [{"panel": i, "title": f"T{i}", "scene_description": f"S{i}", "image_prompt": f"I{i}"} for i in range(1, 6)]})


def good_story_json():
    return json.dumps({"panels": [{"panel": i, "caption": f"C{i}", "narration": f"N{i}",
                                   "dialogue": [{"speaker": "Finn", "text": f"Hi {i}"}]} for i in range(1, 6)]})


# ---------------------------------------------------------------- helpers
def test_extract_json_handles_fences_and_prose():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! Here it is: {"a": [1, 2]} hope it helps') == {"a": [1, 2]}
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_clean_text_removes_markdown_and_emoji():
    assert clean_text("**Bold** 🦊 text", True) == "Bold  text"
    assert "?" in clean_text("caf\u00e9 \u4e2d", False)


def test_request_validation():
    assert ComicRequest(**FORM).tone == "funny"
    assert ComicRequest(**dict(FORM, tone="Light Hearted")).tone == "light-hearted"
    with pytest.raises(ValidationError):
        ComicRequest(**dict(FORM, setting="mars"))
    with pytest.raises(ValidationError):
        ComicRequest(**dict(FORM, prompt="hi"))
    with pytest.raises(ValidationError):
        ComicRequest(**dict(FORM, character_name="   "))


# ---------------------------------------------------------------- text generation
def test_outline_and_story_from_gemini(monkeypatch):
    monkeypatch.setattr(gemini_flash, "generate_text", lambda *a, **k: "```json\n" + good_outline_json() + "\n```")
    monkeypatch.setattr(gemini_pro, "generate_text", lambda *a, **k: good_story_json())
    outline = gemini_flash.generate_outline("idea", "Finn")
    assert outline["source"] == "gemini" and len(outline["panels"]) == 5
    story = gemini_pro.generate_story(outline, "Finn", "funny")
    assert [s["panel"] for s in story] == [1, 2, 3, 4, 5]


def test_malformed_gemini_output_falls_back_offline(monkeypatch):
    monkeypatch.setattr(gemini_flash, "generate_text", lambda *a, **k: "this is not json")
    outline = gemini_flash.generate_outline("A fox", "Finn", "forest", "funny", "anime", idea="A fox")
    assert outline["source"] == "offline" and len(outline["panels"]) == 5
    story = gemini_pro.generate_story(outline, "Finn", "funny")
    assert len(story) == 5 and all(s["dialogue"] for s in story)


def test_too_few_panels_is_rejected():
    with pytest.raises(ValueError):
        gemini_flash.normalize_outline({"panels": [{"title": "x", "scene_description": "y", "image_prompt": "z"}]})


# ---------------------------------------------------------------- full pipeline
def test_pipeline_offline_creates_everything():
    record = run_pipeline(ComicRequest(**FORM))
    assert len(record["layout"]) == 5
    assert (config.BASE_DIR / record["pdf_path"]).stat().st_size > 5000
    for panel in record["layout"]:
        assert (config.BASE_DIR / panel["image_path"]).exists()
    assert record["warnings"]  # offline story + placeholder images are reported to the user


def test_pipeline_uses_gemini_text_when_available(monkeypatch):
    monkeypatch.setattr(gemini_flash, "generate_text", lambda *a, **k: good_outline_json())
    monkeypatch.setattr(gemini_pro, "generate_text", lambda *a, **k: good_story_json())
    record = run_pipeline(ComicRequest(**FORM))
    assert record["meta"]["title"] == "Finn & the Forest"
    assert record["layout"][2]["narration"] == "N3"
    assert record["layout"][2]["dialogue"][0]["text"] == "Hi 3"


# ---------------------------------------------------------------- web routes
def test_home_page_renders_all_options():
    html = client.get("/").text
    for word in ("Castle", "Ocean", "Mysterious", "Pixel art", "Your story idea"):
        assert word in html
    assert client.get("/health").json()["status"] == "ok"


def test_form_flow_preview_download_and_success():
    response = client.post("/generate", data=FORM, follow_redirects=False)
    assert response.status_code == 303
    comic_url = response.headers["location"]
    comic_id = comic_url.rsplit("/", 1)[1]

    preview = client.get(comic_url)
    assert preview.status_code == 200 and "Panel" not in "" and "Download PDF" in preview.text
    assert client.get(f"/export-success/{comic_id}").status_code == 200
    pdf = client.get(f"/download/{comic_id}")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_json_api():
    response = client.post("/generate-comic/json", json=FORM)
    assert response.status_code == 200
    body = response.json()
    assert len(body["layout"]) == 5 and body["pdf_path"].endswith(".pdf")
    bad = client.post("/generate-comic/json", json=dict(FORM, style="3d"))
    assert bad.status_code == 422 and "detail" in bad.json()


def test_background_job_flow():
    start = client.post("/api/jobs", data=FORM)
    assert start.status_code == 200
    job_id = start.json()["job_id"]
    for _ in range(100):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "running":
            break
        time.sleep(0.2)
    assert job["status"] == "done" and job["comic_id"]
    assert client.get(f"/comic/{job['comic_id']}").status_code == 200


def test_job_validation_and_unknown_job():
    assert client.post("/api/jobs", data=dict(FORM, setting="mars")).status_code == 422
    assert client.get("/api/jobs/abcdefabcdef").status_code == 404


def test_error_pages():
    page = client.get("/comic/doesnotexist")
    assert page.status_code == 404 and "not found" in page.text.lower()
    assert client.get("/comic/../../etc/passwd").status_code == 404
    assert client.get("/download/aaaaaaaaaaaa").status_code == 404
    assert client.post("/generate", data={"prompt": "x"}).status_code == 422


def test_test_image_endpoint():
    body = client.get("/test-image", params={"prompt": "a castle"}).json()
    assert body["source"] == "placeholder" and (config.BASE_DIR / body["path"]).exists()
