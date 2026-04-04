from __future__ import annotations

from contextlib import asynccontextmanager
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .analysis import AnalysisError, VisionAnalyzer
from .config import PROJECT_ROOT, Settings, get_settings
from .jobs import AnalysisJobStore
from .models import AnalysisJob, SessionAnalysis
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
    app.state.analyzer = VisionAnalyzer(settings)
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
        except Exception:
            app.state.jobs.fail(job_id, "Unexpected analysis failure.")
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
    async def health() -> dict[str, str]:
        return {"status": "ok"}

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
