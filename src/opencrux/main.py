from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import shutil
import traceback
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .analysis import AnalysisError, VisionAnalyzer
from .config import PROJECT_ROOT, Settings, get_settings
from .db import Database
from .jobs import AnalysisJobStore
from .models import AnalysisJob, SessionAnalysis
from .pose_store import PoseStore
from .store import SessionStore


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def safe_filename(filename: str) -> str:
    cleaned = "".join(character if character.isalnum() or character in {"-", "_", "."} else "-" for character in filename)
    return cleaned or "upload.mp4"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.session_dir.mkdir(parents=True, exist_ok=True)
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        app.state.jobs.shutdown()

    app = FastAPI(title="OpenCrux", version="0.1.0", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.state.settings = settings
    app.state.store = SessionStore(settings.session_dir)
    db = Database(settings.db_path)
    app.state.db = db
    app.state.pose_store = PoseStore(db)
    app.state.analyzer = VisionAnalyzer(settings, pose_store=app.state.pose_store)
    app.state.jobs = AnalysisJobStore(max_preview_frames=settings.preview_history_limit)
    app.state.templates = templates

    def persist_analysis(analysis: SessionAnalysis, destination: Path) -> SessionAnalysis:
        try:
            stored_video_path = str(destination.relative_to(PROJECT_ROOT))
        except ValueError:
            stored_video_path = str(destination)

        stored_analysis = analysis.model_copy(update={"stored_video_path": stored_video_path})
        app.state.store.save(stored_analysis)
        return stored_analysis

    def run_analysis_job(
        *,
        job_id: str,
        destination: Path,
        original_filename: str,
        route_name: str | None,
        gym_name: str | None,
    ) -> None:
        app.state.jobs.mark_running(job_id, stage="Opening video and preparing pose model.")
        try:
            analysis = app.state.analyzer.analyze(
                destination,
                session_id=uuid4().hex,
                original_filename=original_filename,
                route_name=route_name,
                gym_name=gym_name,
                progress_callback=lambda update: app.state.jobs.update_preview(job_id, update),
            )
            stored_analysis = persist_analysis(analysis, destination)
        except AnalysisError as error:
            app.state.jobs.fail(job_id, str(error))
            return
        except Exception as exc:
            logging.getLogger("opencrux").error(
                "Analysis job %s failed: %s\n%s", job_id, exc, traceback.format_exc()
            )
            app.state.jobs.fail(job_id, f"Unexpected analysis failure: {exc}")
            return

        app.state.jobs.complete(job_id, stored_analysis)

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"request": request},
        )

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/debug/env")
    async def debug_env() -> dict:
        import os
        data_dir = settings.data_dir
        model_path = settings.pose_model_path
        return {
            "data_dir": str(data_dir),
            "data_dir_exists": data_dir.exists() if data_dir else False,
            "models_dir": str(settings.models_dir),
            "upload_dir": str(settings.upload_dir),
            "pose_model_path": str(model_path),
            "pose_model_exists": model_path.exists() if model_path else False,
            "pose_model_size_bytes": model_path.stat().st_size if model_path and model_path.exists() else 0,
            "upload_dir_contents": os.listdir(str(settings.upload_dir)) if settings.upload_dir and settings.upload_dir.exists() else [],
            "OPENCRUX_DATA_DIR": os.environ.get("OPENCRUX_DATA_DIR", "<not set>"),
            "gemma_enabled": settings.gemma_enabled,
            "llm_backend": settings.llm_backend,
            "gemini_api_key_set": bool(settings.gemini_api_key),
            "gemini_model": settings.gemini_model,
            "OPENCRUX_GEMMA_ENABLED": os.environ.get("OPENCRUX_GEMMA_ENABLED", "<not set>"),
            "OPENCRUX_LLM_BACKEND": os.environ.get("OPENCRUX_LLM_BACKEND", "<not set>"),
        }

    @app.get("/api/sessions", response_model=list[SessionAnalysis])
    async def list_sessions(limit: int = 10) -> list[SessionAnalysis]:
        safe_limit = max(1, min(limit, 50))
        return app.state.store.list(limit=safe_limit)

    @app.get("/api/sessions/{session_id}", response_model=SessionAnalysis)
    async def get_session(session_id: str) -> SessionAnalysis:
        session = app.state.store.get(session_id)
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
        return session

    @app.get("/api/analysis-jobs/{job_id}", response_model=AnalysisJob)
    async def get_analysis_job(job_id: str) -> AnalysisJob:
        job = app.state.jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis job not found.")
        return job

    @app.post("/api/analysis-jobs", response_model=AnalysisJob, status_code=status.HTTP_202_ACCEPTED)
    async def create_analysis_job(
        file: UploadFile = File(...),
        route_name: str | None = Form(default=None),
        gym_name: str | None = Form(default=None),
    ) -> AnalysisJob:
        suffix = Path(file.filename or "upload").suffix.lower()
        if suffix not in ALLOWED_VIDEO_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported video type. Use mp4, mov, avi, mkv, or webm.",
            )

        destination = settings.upload_dir / f"{uuid4().hex}-{safe_filename(file.filename or 'upload.mp4')}"
        destination.parent.mkdir(parents=True, exist_ok=True)

        with destination.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        max_bytes = settings.max_upload_mb * 1024 * 1024
        if destination.stat().st_size > max_bytes:
            destination.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Video too large. Maximum size is {settings.max_upload_mb} MB.",
            )

        job = app.state.jobs.create(
            original_filename=file.filename or destination.name,
            route_name=route_name,
            gym_name=gym_name,
        )
        app.state.jobs.submit(
            run_analysis_job,
            job_id=job.id,
            destination=destination,
            original_filename=file.filename or destination.name,
            route_name=route_name,
            gym_name=gym_name,
        )
        return app.state.jobs.get(job.id) or job

    @app.post("/api/sessions/analyze", response_model=SessionAnalysis)
    async def analyze_session(
        file: UploadFile = File(...),
        route_name: str | None = Form(default=None),
        gym_name: str | None = Form(default=None),
    ) -> SessionAnalysis:
        suffix = Path(file.filename or "upload").suffix.lower()
        if suffix not in ALLOWED_VIDEO_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported video type. Use mp4, mov, avi, mkv, or webm.",
            )

        session_id = uuid4().hex
        destination = settings.upload_dir / f"{session_id}-{safe_filename(file.filename or 'upload.mp4')}"
        destination.parent.mkdir(parents=True, exist_ok=True)

        with destination.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        max_bytes = settings.max_upload_mb * 1024 * 1024
        if destination.stat().st_size > max_bytes:
            destination.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Video too large. Maximum size is {settings.max_upload_mb} MB.",
            )

        try:
            analysis = app.state.analyzer.analyze(
                destination,
                session_id=session_id,
                original_filename=file.filename or destination.name,
                route_name=route_name,
                gym_name=gym_name,
            )
        except AnalysisError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
        except Exception as error:  # pragma: no cover - defensive guard for the first slice
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected analysis failure.") from error

        return persist_analysis(analysis, destination)

    return app


app = create_app()
