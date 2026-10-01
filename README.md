# ComicCraft – AI Comic Story Creator

Type a story idea, pick a character, setting, tone and art style, and ComicCraft builds a 5-panel comic:

| Step | Module | What happens |
|---|---|---|
| 1 | `app/gemini_flash.py` | Gemini Flash plans 5 panels (title, scene, image prompt, fixed character look) |
| 2 | `app/gemini_pro.py` | Gemini Pro writes captions, narration and dialogue per panel |
| 3 | `app/image_generator.py` | Hugging Face (FLUX / SDXL) draws each panel, in parallel |
| 4 | `app/layout_builder.py` | Matches text and images by panel number |
| 5 | `app/exporters.py` | FPDF2 exports a PDF (cover + one page per panel) |

Frontend: Jinja2 templates + `static/css/style.css` + `static/js/app.js` (live progress bar while the comic is generated).

## Run it (Windows / VS Code)

```
python -m venv comiccraft-env
comiccraft-env\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Open `.env` and add your keys:

- `GEMINI_API_KEY` – free at https://aistudio.google.com/app/apikey
- `HF_API_KEY` – https://huggingface.co/settings/tokens (token needs the *Inference Providers* permission)

Start the server from the project root (the folder that contains `app/` and `templates/`):

```
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 (API docs: http://127.0.0.1:8000/docs).
macOS/Linux: use `python3 -m venv env && source env/bin/activate` and `cp .env.example .env`.
In VS Code you can also press F5 (a launch config is included).

## Routes

| Route | Purpose |
|---|---|
| `GET /` | Input form |
| `POST /generate` | Form submit without JavaScript: builds the comic, redirects to the preview |
| `POST /api/jobs`, `GET /api/jobs/{id}` | Background generation + progress (used by the web page) |
| `POST /generate-comic/json` | JSON API: returns layout + PDF path |
| `GET /comic/{id}` | Comic preview |
| `GET /export-success/{id}` | Success page, starts the PDF download |
| `GET /download/{id}` | The PDF file |
| `GET /test-image?prompt=...` | Test image generation alone |
| `GET /health` | Shows whether the keys are set |

## Built to not crash

- Gemini model names are checked against what your key can use; unavailable ones are skipped and temporary 429/503 errors are retried.
- If Gemini is unavailable, a simple built-in story is used (a warning banner tells you).
- Images try Hugging Face first, then a free keyless service (`image.pollinations.ai`, set `ENABLE_FREE_IMAGE_FALLBACK=false` to turn this off — it receives the image prompt), then a drawn placeholder.
- All input is validated; errors show a readable page instead of a stack trace.

AI output quality (story and pictures) varies between runs and cannot be guaranteed. What is guaranteed is that you always get a complete comic and PDF.

## Tests

```
pip install -r requirements-dev.txt
pytest -q
```
The tests run fully offline (no keys, no network).

## Troubleshooting

- **Placeholder images** – `HF_API_KEY` missing, token lacks Inference Providers permission, or the free quota is used up (see the server console).
- **"Gemini was unavailable" banner** – check `GEMINI_API_KEY`, then the server console for the exact error.
- **Generated files** – panel images in `static/panels/`, PDFs in `static/exports/`, comic data in `storage/comics/`.
