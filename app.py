import base64
import json
import os
import re
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

import Interlude


BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
DIST_DIR = BASE_DIR / "dist"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
MEDIA_DIR = BASE_DIR / "media"
MEDIA_DIR.mkdir(exist_ok=True)
PROJECT_STORE_PATH = Path(
    os.getenv("INTERLUDE_PROJECT_STORE", Path.home() / ".interlude" / "projects.json")
)

ALLOWED_EXTENSIONS = {
    ".aiff",
    ".aif",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".wav",
}


def load_projects():
    if not PROJECT_STORE_PATH.exists():
        return {}

    try:
        with PROJECT_STORE_PATH.open("r", encoding="utf-8") as project_file:
            data = json.load(project_file)
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(data, dict):
        return {}

    projects = data.get("projects", {})

    if not isinstance(projects, dict):
        return {}

    return projects


def save_projects():
    PROJECT_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = PROJECT_STORE_PATH.with_suffix(".tmp")

    with temporary_path.open("w", encoding="utf-8") as project_file:
        json.dump({"projects": PROJECTS}, project_file, ensure_ascii=False)

    temporary_path.replace(PROJECT_STORE_PATH)


PROJECTS = load_projects()

app = FastAPI(title="Interlude")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

if (DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")


class AnalyzeRequest(BaseModel):
    filename: str
    file_data: str
    extra_prompt: str = ""
    root: str | None = None
    scale_type: str | None = None
    separate_vocals: bool = False


class FollowUpRequest(BaseModel):
    project_id: str
    question: str


def clean_choice(value):
    if value in (None, "", "auto"):
        return None

    return value


def safe_upload_path(filename):
    original_name = Path(filename).name
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", original_name)
    suffix = Path(safe_name).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        supported = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio file type. Use one of: {supported}",
        )

    return UPLOAD_DIR / f"{uuid.uuid4().hex}_{safe_name}"


def decode_file(file_data):
    try:
        if "," in file_data:
            file_data = file_data.split(",", 1)[1]

        return base64.b64decode(file_data, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid uploaded file data") from exc


@app.get("/")
async def index():
    if (DIST_DIR / "index.html").exists():
        return FileResponse(DIST_DIR / "index.html")

    raise HTTPException(
        status_code=503,
        detail="React build not found. Run npm run build or npm run dev.",
    )


@app.get("/api/options")
async def options():
    return {
        "roots": list(Interlude.NOTE_TO_INDEX.keys()),
        "scales": sorted(Interlude.SCALE_PATTERNS.keys()),
        "capabilities": {
            "vocal_separation": {
                "available": Interlude.vocal_separation_available(),
                "model": Interlude.VOCAL_SEPARATION_MODEL,
            },
        },
    }


@app.post("/api/analyze")
async def analyze(request: AnalyzeRequest):
    root = clean_choice(request.root)
    scale_type = clean_choice(request.scale_type)

    if request.separate_vocals and not Interlude.vocal_separation_available():
        raise HTTPException(
            status_code=503,
            detail=(
                "Vocal separation is unavailable. Install requirements-vocal.txt "
                "and restart Interlude."
            ),
        )

    if bool(root) != bool(scale_type):
        raise HTTPException(
            status_code=400,
            detail="Choose both a root and scale/mode, or leave both set to auto.",
        )

    if root and root not in Interlude.NOTE_TO_INDEX:
        raise HTTPException(status_code=400, detail="Unsupported root selection.")

    if scale_type and scale_type not in Interlude.SCALE_PATTERNS:
        raise HTTPException(status_code=400, detail="Unsupported scale/mode selection.")

    upload_path = safe_upload_path(request.filename)
    upload_path.write_bytes(decode_file(request.file_data))

    media_path = None

    try:
        try:
            result = await run_in_threadpool(
                Interlude.run_interlude_analysis,
                str(upload_path),
                root,
                scale_type,
                request.extra_prompt,
                request.separate_vocals,
            )
        except Interlude.AnalysisInputError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Interlude.VocalSeparationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        project_id = uuid.uuid4().hex
        original_name = Path(request.filename).name
        media_path = MEDIA_DIR / f"{project_id}{upload_path.suffix.lower()}"
        shutil.copyfile(upload_path, media_path)

        result["project"]["id"] = project_id
        result["project"]["title"] = Path(original_name).stem
        result["project"]["filename"] = original_name
        result["project"]["audio_url"] = f"/media/{media_path.name}"
        PROJECTS[project_id] = result

        try:
            save_projects()
        except Exception:
            PROJECTS.pop(project_id, None)
            media_path.unlink(missing_ok=True)
            raise

        return result
    finally:
        upload_path.unlink(missing_ok=True)


@app.get("/api/projects")
async def projects():
    return {
        "projects": [
            {
                "id": project_id,
                "title": item["project"]["title"],
                "filename": item["project"]["filename"],
                "created_at": item["project"]["created_at"],
                "duration": item["project"]["duration"],
                "key": item["key"],
                "scores": item["scores"],
            }
            for project_id, item in reversed(PROJECTS.items())
        ]
    }


@app.get("/api/projects/{project_id}")
async def project_detail(project_id: str):
    project = PROJECTS.get(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    return project


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    if project_id not in PROJECTS:
        raise HTTPException(status_code=404, detail="Project not found.")

    project = PROJECTS.pop(project_id)
    audio_url = project.get("project", {}).get("audio_url")

    if isinstance(audio_url, str) and audio_url.startswith("/media/"):
        (MEDIA_DIR / Path(audio_url).name).unlink(missing_ok=True)

    save_projects()

    return {"deleted": project_id}


@app.post("/api/follow-up")
async def follow_up(request: FollowUpRequest):
    project = PROJECTS.get(request.project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    context = (
        f"Project: {project['project']['title']}\n"
        f"Summary: {project['summary']}\n"
        f"Scores: {project['scores']}\n"
        f"Key: {project['key']}\n"
        f"Feedback: {project['response']}\n"
    )
    result = await run_in_threadpool(
        Interlude.ask_follow_up,
        context,
        request.question,
    )

    return result
