from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import config
from app.routes import router, templates

config.ensure_dirs()

app = FastAPI(title="ComicCraft", description="AI comic story creator (Gemini + image models + PDF export)")
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")
app.include_router(router)


def _wants_json(request: Request) -> bool:
    path = request.url.path
    return path.startswith("/api") or path.endswith("/json") or "application/json" in request.headers.get("accept", "").split(",")[0]


def _error(request: Request, status: int, message: str):
    if _wants_json(request):
        return JSONResponse(status_code=status, content={"detail": message})
    return templates.TemplateResponse(request, "error.html", {"status": status, "message": message}, status_code=status)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "Something went wrong."
    if exc.status_code == 404 and message == "Not Found":
        message = "That page does not exist."
    return _error(request, exc.status_code, message)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    fields = ", ".join(sorted({str(e["loc"][-1]) for e in exc.errors() if e.get("loc")})) or "input"
    return _error(request, 422, f"Please check these fields and try again: {fields}.")


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    return _error(request, 500, "Unexpected server error. Please try again.")
