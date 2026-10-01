import threading
import traceback
from typing import Dict

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app import config
from app.image_generator import generate_image_with_source
from app.pipeline import run_pipeline
from app.schemas import ComicRequest
from app.storage import is_valid_id, jobs, load_comic

router = APIRouter()
templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


def _form_context() -> Dict:
    return {
        "settings": config.SETTINGS, "tones": config.TONES, "styles": config.STYLES,
        "samples": config.SAMPLE_IDEAS,
        "gemini_ready": bool(config.GEMINI_API_KEY), "hf_ready": bool(config.HF_API_KEY),
    }


def _validation_message(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err.get("loc", ())) or "input"
        parts.append(f"{field}: {err.get('msg', 'invalid value')}")
    return "; ".join(parts)


def _get_comic_or_404(comic_id: str) -> Dict:
    record = load_comic(comic_id)
    if record is None:
        raise HTTPException(status_code=404, detail="That comic was not found. It may have been deleted.")
    return record


# ------------------------------------------------------------------ pages
@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", _form_context())


@router.post("/generate")
def generate_comic(
    prompt: str = Form(...), character_name: str = Form(...), setting: str = Form("forest"),
    tone: str = Form("dramatic"), style: str = Form("comic book"),
):
    """Classic form submit (works without JavaScript): builds the comic, then redirects to its preview."""
    try:
        req = ComicRequest(prompt=prompt, character_name=character_name, setting=setting, tone=tone, style=style)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_validation_message(exc))
    try:
        record = run_pipeline(req)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Comic generation failed: {exc}")
    return RedirectResponse(url=f"/comic/{record['id']}", status_code=303)


@router.get("/comic/{comic_id}", response_class=HTMLResponse)
def comic_preview(request: Request, comic_id: str):
    record = _get_comic_or_404(comic_id)
    return templates.TemplateResponse(request, "comic_preview.html", {"comic": record, "layout": record["layout"], "meta": record["meta"]})


@router.get("/download/{comic_id}")
def download_pdf(comic_id: str):
    record = _get_comic_or_404(comic_id)
    path = config.BASE_DIR / record["pdf_path"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="The PDF file is missing. Please generate the comic again.")
    safe_title = "".join(c for c in record["meta"].get("title", "comic") if c.isalnum() or c in " -_").strip() or "comic"
    return FileResponse(str(path), media_type="application/pdf", filename=f"{safe_title}.pdf")


@router.get("/export-success/{comic_id}", response_class=HTMLResponse)
def export_success(request: Request, comic_id: str):
    record = _get_comic_or_404(comic_id)
    return templates.TemplateResponse(request, "export_success.html", {"comic": record, "meta": record["meta"]})


# ------------------------------------------------------------------ JSON API
@router.post("/generate-comic/json")
def generate_comic_json(payload: ComicRequest):
    try:
        record = run_pipeline(payload)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Comic generation failed: {exc}")
    return {"id": record["id"], "layout": record["layout"], "pdf_path": record["pdf_path"],
            "warnings": record["warnings"], "preview_url": f"/comic/{record['id']}"}


@router.post("/api/jobs")
def start_job(prompt: str = Form(...), character_name: str = Form(...), setting: str = Form("forest"),
              tone: str = Form("dramatic"), style: str = Form("comic book")):
    """Start generation in the background; the browser polls /api/jobs/{id} for progress."""
    try:
        req = ComicRequest(prompt=prompt, character_name=character_name, setting=setting, tone=tone, style=style)
    except ValidationError as exc:
        return JSONResponse(status_code=422, content={"detail": _validation_message(exc)})

    job_id = jobs.create()

    def work():
        try:
            record = run_pipeline(req, progress=lambda pct, msg: jobs.update(job_id, progress=pct, message=msg))
            jobs.update(job_id, status="done", progress=100, message="Done!", comic_id=record["id"])
        except Exception as exc:  # never leave the browser waiting forever
            traceback.print_exc()
            jobs.update(job_id, status="error", error=f"Comic generation failed: {exc}")

    threading.Thread(target=work, daemon=True).start()
    return {"job_id": job_id}


@router.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = jobs.get(job_id) if is_valid_id(job_id) else None
    if job is None:
        return JSONResponse(status_code=404, content={"detail": "Unknown job. Please start again."})
    return {k: job[k] for k in ("id", "status", "progress", "message", "comic_id", "error")}


@router.get("/test-image")
def test_image(prompt: str = "A futuristic city at sunset, sci-fi, cinematic"):
    prompt = prompt[:500]
    path, source = generate_image_with_source(prompt, label=prompt)
    return {"message": "Image generated successfully", "path": path, "source": source}


@router.get("/health")
def health():
    return {"status": "ok", "gemini_key_set": bool(config.GEMINI_API_KEY), "hf_key_set": bool(config.HF_API_KEY)}
