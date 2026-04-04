import asyncio
import shutil
import socket
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import URLError
from urllib.request import urlopen

import pytest
import uvicorn
from fastapi.responses import JSONResponse
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from opencrux.analysis import AnalysisError, AnalysisPreviewUpdate
from opencrux.config import Settings
from opencrux.main import create_app
from opencrux.models import (
    AttemptSummary,
    PreviewAttemptWindow,
    ProcessingWarning,
    SessionAnalysis,
    SessionMetrics,
    SessionStatus,
)


CHROMIUM_BINARY = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
CHROMEDRIVER_BINARY = shutil.which("chromedriver")
TEST_TIMEOUT_SECONDS = 12
CREATE_JOB_RESPONSE_DELAY_SECONDS = 0.8


def make_metrics() -> SessionMetrics:
    return SessionMetrics(
        attempt_count=1,
        estimated_time_on_wall_seconds=8.2,
        average_rest_seconds=0.0,
        total_rest_seconds=0.0,
        lateral_span_ratio=0.19,
        vertical_progress_ratio=0.32,
        hesitation_marker_count=0,
        mean_pose_visibility=0.81,
    )


def make_attempt() -> AttemptSummary:
    return AttemptSummary(
        index=1,
        start_seconds=0.0,
        end_seconds=8.2,
        duration_seconds=8.2,
        vertical_progress_ratio=0.32,
        lateral_span_ratio=0.19,
    )


def make_session(
    session_id: str,
    original_filename: str,
    *,
    warnings: list[ProcessingWarning] | None = None,
) -> SessionAnalysis:
    return SessionAnalysis(
        id=session_id,
        status=SessionStatus.COMPLETED,
        original_filename=original_filename,
        stored_video_path=f"data/uploads/{original_filename}",
        source_duration_seconds=9.5,
        sampled_fps=6.0,
        warnings=warnings or [],
        attempts=[make_attempt()],
        metrics=make_metrics(),
    )


class BrowserSmokeAnalyzer:
    def analyze(self, video_path: Path, **kwargs: object) -> SessionAnalysis:
        progress_callback = kwargs.get("progress_callback")
        session_id = str(kwargs.get("session_id") or video_path.stem)
        original_filename = str(kwargs.get("original_filename") or video_path.name)
        clip_name = Path(original_filename).stem

        if callable(progress_callback):
            if clip_name == "poll-never-recovers":
                progress_callback(
                    AnalysisPreviewUpdate(
                        progress_ratio=0.25,
                        processed_frame_count=2,
                        total_frame_count=10,
                        current_timestamp_seconds=0.32,
                        detected_pose_count=1,
                        visible_landmark_count=17,
                        multi_pose_ratio=0.0,
                        coverage_ratio=0.64,
                        mean_pose_visibility=0.8,
                        provisional_attempt_count=1,
                        provisional_vertical_progress_ratio=0.17,
                        provisional_lateral_span_ratio=0.07,
                        stage="Sampling frames and fitting pose landmarks.",
                        last_update_message="Frame 2/10 at 0.32s",
                        preview_image_base64="ZmFrZS1wcmV2aWV3",
                        provisional_attempts=[
                            PreviewAttemptWindow(index=1, start_seconds=0.0, end_seconds=0.32, duration_seconds=0.32)
                        ],
                    )
                )
                time.sleep(7.0)
                return make_session(session_id, original_filename)

            if clip_name == "negative":
                progress_callback(
                    AnalysisPreviewUpdate(
                        progress_ratio=0.45,
                        processed_frame_count=5,
                        total_frame_count=10,
                        current_timestamp_seconds=0.9,
                        detected_pose_count=2,
                        visible_landmark_count=14,
                        multi_pose_ratio=0.6,
                        coverage_ratio=0.41,
                        mean_pose_visibility=0.54,
                        provisional_attempt_count=1,
                        provisional_vertical_progress_ratio=0.18,
                        provisional_lateral_span_ratio=0.1,
                        stage="Sampling frames and fitting pose landmarks.",
                        last_update_message="Frame 5/10 at 0.90s",
                        preview_image_base64="ZmFrZS1wcmV2aWV3LW5lZ2F0aXZl",
                        provisional_attempts=[
                            PreviewAttemptWindow(index=1, start_seconds=0.0, end_seconds=0.9, duration_seconds=0.9)
                        ],
                        active_warnings=[
                            ProcessingWarning(
                                code="multiple_people_dominant",
                                message="Multiple climbers are dominating sampled frames. This clip is likely unsupported for the current slice.",
                                severity="error",
                            )
                        ],
                    )
                )
                time.sleep(0.35)
                raise AnalysisError(
                    "OpenCrux detected multiple climbers for a substantial portion of this clip. The current slice only supports one dominant climber per video."
                )

            progress_callback(
                AnalysisPreviewUpdate(
                    progress_ratio=0.3,
                    processed_frame_count=3,
                    total_frame_count=10,
                    current_timestamp_seconds=0.48,
                    detected_pose_count=1,
                    visible_landmark_count=18,
                    multi_pose_ratio=0.0,
                    coverage_ratio=0.67,
                    mean_pose_visibility=0.82,
                    provisional_attempt_count=1,
                    provisional_vertical_progress_ratio=0.21,
                    provisional_lateral_span_ratio=0.08,
                    stage="Sampling frames and fitting pose landmarks.",
                    last_update_message="Frame 3/10 at 0.48s",
                    preview_image_base64="ZmFrZS1wcmV2aWV3",
                    provisional_attempts=[
                        PreviewAttemptWindow(index=1, start_seconds=0.0, end_seconds=0.48, duration_seconds=0.48)
                    ],
                    active_warnings=(
                        [
                            ProcessingWarning(
                                code="low_pose_coverage",
                                message="Pose coverage is intermittent enough that this run should be reviewed with caution.",
                            )
                        ]
                        if clip_name == "caution"
                        else []
                    ),
                )
            )

        time.sleep(1.05)
        warnings = (
            [
                ProcessingWarning(
                    code="low_pose_coverage",
                    message="Pose coverage is intermittent enough that this run should be reviewed with caution.",
                )
            ]
            if clip_name == "caution"
            else []
        )
        return make_session(session_id, original_filename, warnings=warnings)


def wait_for_server(base_url: str) -> None:
    deadline = time.monotonic() + TEST_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            with urlopen(f"{base_url}/api/health") as response:
                if response.status == 200:
                    return
        except URLError:
            time.sleep(0.05)
    raise AssertionError("Timed out waiting for the temporary OpenCrux app to start.")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def running_browser_smoke_app():
    with TemporaryDirectory() as directory:
        settings = Settings(
            data_dir=Path(directory),
            upload_dir=Path(directory) / "uploads",
            session_dir=Path(directory) / "sessions",
        )
        app = create_app(settings)
        app.state.analyzer = BrowserSmokeAnalyzer()
        app.state.store.save(make_session("seeded-history", "seeded-history.mp4"))

        @app.middleware("http")
        async def delay_create_job_response(request, call_next):
            if request.method == "POST" and request.url.path == "/api/analysis-jobs":
                await asyncio.sleep(CREATE_JOB_RESPONSE_DELAY_SECONDS)
                response = await call_next(request)
                create_fail_job = next(
                    (job for job in app.state.jobs._jobs.values() if job.original_filename == "create-fail.mp4"),
                    None,
                )
                if create_fail_job is not None:
                    return JSONResponse(
                        {"detail": "Create-job response interrupted after submission."},
                        status_code=503,
                    )
                return response
            if request.method == "GET" and request.url.path.startswith("/api/analysis-jobs/"):
                job_id = request.url.path.rsplit("/", 1)[-1]
                job = app.state.jobs.get(job_id)
                if job is not None and job.original_filename in {"poll-fail.mp4", "poll-never-recovers.mp4"}:
                    return JSONResponse({"detail": "Temporary poll failure."}, status_code=503)
            return await call_next(request)

        port = free_port()
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{port}"

        try:
            wait_for_server(base_url)
            yield base_url, Path(directory)
        finally:
            server.should_exit = True
            thread.join(timeout=5)


@pytest.fixture
def browser_smoke_app():
    with running_browser_smoke_app() as context:
        yield context


@pytest.fixture
def chrome_driver():
    if CHROMIUM_BINARY is None or CHROMEDRIVER_BINARY is None:
        pytest.skip("Chromium and chromedriver are required for the browser smoke test.")

    options = Options()
    options.binary_location = CHROMIUM_BINARY
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,1200")
    driver = webdriver.Chrome(service=Service(CHROMEDRIVER_BINARY), options=options)
    try:
        yield driver
    finally:
        driver.quit()


def create_dummy_clip(directory: Path, stem: str) -> Path:
    clip_path = directory / f"{stem}.mp4"
    clip_path.write_bytes(b"opencrux-browser-smoke")
    return clip_path


def wait_for_text(driver: webdriver.Chrome, selector: str, expected_text: str) -> None:
    WebDriverWait(driver, TEST_TIMEOUT_SECONDS).until(
        lambda current_driver: current_driver.find_element(By.CSS_SELECTOR, selector).text == expected_text
    )


def wait_for_contains(driver: webdriver.Chrome, selector: str, expected_fragment: str) -> None:
    WebDriverWait(driver, TEST_TIMEOUT_SECONDS).until(
        lambda current_driver: expected_fragment in current_driver.find_element(By.CSS_SELECTOR, selector).text
    )


def wait_for_verdict(driver: webdriver.Chrome, verdict: str) -> None:
    WebDriverWait(driver, TEST_TIMEOUT_SECONDS).until(
        lambda current_driver: current_driver.find_element(By.ID, "analysis-workspace").get_attribute("data-verdict") == verdict
    )


def history_items(driver: webdriver.Chrome):
    return driver.find_elements(By.CSS_SELECTOR, "#history-list .history-item")


def history_contains_filename(driver: webdriver.Chrome, filename: str) -> bool:
    try:
        return any(filename in item.text for item in history_items(driver))
    except StaleElementReferenceException:
        return False


def click_history_item(driver: webdriver.Chrome, filename: str) -> None:
    deadline = time.monotonic() + TEST_TIMEOUT_SECONDS
    last_error: StaleElementReferenceException | None = None

    while time.monotonic() < deadline:
        try:
            for item in history_items(driver):
                if filename in item.text and item.is_enabled():
                    item.click()
                    return
        except StaleElementReferenceException as error:
            last_error = error

        time.sleep(0.05)

    if last_error is not None:
        raise AssertionError(f"Timed out clicking refreshed history item for {filename}.") from last_error
    raise AssertionError(f"Timed out finding enabled history item for {filename}.")


def submit_clip(driver: webdriver.Chrome, clip_path: Path) -> None:
    file_input = driver.find_element(By.ID, "video-file")
    file_input.send_keys(str(clip_path))
    driver.find_element(By.ID, "submit-button").click()


def assert_intake_controls_disabled(driver: webdriver.Chrome) -> None:
    assert not driver.find_element(By.ID, "submit-button").is_enabled()
    assert not driver.find_element(By.ID, "refresh-history-button").is_enabled()
    assert driver.find_element(By.ID, "video-file").get_attribute("disabled") is not None
    assert driver.find_element(By.CSS_SELECTOR, 'input[name="route_name"]').get_attribute("disabled") is not None
    assert driver.find_element(By.CSS_SELECTOR, 'input[name="gym_name"]').get_attribute("disabled") is not None


def test_browser_smoke_protected_lifecycle(browser_smoke_app, chrome_driver: webdriver.Chrome) -> None:
    base_url, temp_dir = browser_smoke_app
    chrome_driver.get(base_url)

    wait_for_text(chrome_driver, "#workspace-status-label", "Idle")
    WebDriverWait(chrome_driver, TEST_TIMEOUT_SECONDS).until(lambda driver: len(history_items(driver)) == 1)

    submission_started = time.monotonic()
    submit_clip(chrome_driver, create_dummy_clip(temp_dir, "ready"))

    WebDriverWait(chrome_driver, 0.4).until(
        lambda driver: not driver.find_element(By.ID, "submit-button").is_enabled()
    )
    assert time.monotonic() - submission_started < CREATE_JOB_RESPONSE_DELAY_SECONDS
    WebDriverWait(chrome_driver, 0.4).until(
        lambda driver: not driver.find_element(By.ID, "refresh-history-button").is_enabled()
    )
    WebDriverWait(chrome_driver, 0.4).until(
        lambda driver: not history_items(driver)[0].is_enabled()
    )
    assert chrome_driver.find_element(By.ID, "video-file").get_attribute("disabled") is not None
    assert chrome_driver.find_element(By.CSS_SELECTOR, 'input[name="route_name"]').get_attribute("disabled") is not None
    assert chrome_driver.find_element(By.CSS_SELECTOR, 'input[name="gym_name"]').get_attribute("disabled") is not None
    wait_for_text(chrome_driver, "#status", "Creating analysis job.")
    wait_for_text(chrome_driver, "#session-title", "ready.mp4")
    wait_for_verdict(chrome_driver, "analyzing")
    assert_intake_controls_disabled(chrome_driver)
    assert not history_items(chrome_driver)[0].is_enabled()
    wait_for_contains(chrome_driver, "#status", "Sampling frames and fitting pose landmarks.")
    wait_for_verdict(chrome_driver, "ready")
    wait_for_text(chrome_driver, "#verdict-title", "Supported run")
    WebDriverWait(chrome_driver, TEST_TIMEOUT_SECONDS).until(
        lambda driver: driver.find_element(By.ID, "refresh-history-button").is_enabled()
    )

    chrome_driver.find_element(By.ID, "refresh-history-button").click()
    WebDriverWait(chrome_driver, TEST_TIMEOUT_SECONDS).until(lambda driver: len(history_items(driver)) >= 2)
    WebDriverWait(chrome_driver, TEST_TIMEOUT_SECONDS).until(
        lambda driver: history_contains_filename(driver, "ready.mp4")
    )
    click_history_item(chrome_driver, "ready.mp4")
    wait_for_text(
        chrome_driver,
        "#preview-empty",
        "Stored sessions keep metrics and warnings, but annotated preview frames are not persisted in Phase 1.",
    )
    wait_for_text(chrome_driver, "#session-title", "ready.mp4")

    submit_clip(chrome_driver, create_dummy_clip(temp_dir, "caution"))
    wait_for_verdict(chrome_driver, "analyzing")
    wait_for_verdict(chrome_driver, "caution")
    wait_for_text(chrome_driver, "#verdict-title", "Review with caution")

    submit_clip(chrome_driver, create_dummy_clip(temp_dir, "negative"))
    wait_for_verdict(chrome_driver, "analyzing")
    wait_for_verdict(chrome_driver, "negative")
    wait_for_contains(chrome_driver, "#verdict-title", "Unsupported footage")
    wait_for_contains(chrome_driver, "#verdict-message", "one dominant climber")
    WebDriverWait(chrome_driver, TEST_TIMEOUT_SECONDS).until(
        lambda driver: driver.find_element(By.ID, "submit-button").is_enabled()
    )


def test_browser_smoke_recovers_from_poll_failure(browser_smoke_app, chrome_driver: webdriver.Chrome) -> None:
    base_url, temp_dir = browser_smoke_app
    chrome_driver.get(base_url)

    wait_for_text(chrome_driver, "#workspace-status-label", "Idle")
    WebDriverWait(chrome_driver, TEST_TIMEOUT_SECONDS).until(lambda driver: len(history_items(driver)) == 1)
    submit_clip(chrome_driver, create_dummy_clip(temp_dir, "poll-fail"))

    wait_for_contains(chrome_driver, "#status", "Temporary poll failure.")
    assert_intake_controls_disabled(chrome_driver)
    assert not history_items(chrome_driver)[0].is_enabled()
    wait_for_contains(chrome_driver, "#status", "Recovered completed session")
    wait_for_verdict(chrome_driver, "ready")
    wait_for_text(chrome_driver, "#session-title", "poll-fail.mp4")
    wait_for_text(
        chrome_driver,
        "#preview-empty",
        "Stored sessions keep metrics and warnings, but annotated preview frames are not persisted in Phase 1.",
    )
    WebDriverWait(chrome_driver, TEST_TIMEOUT_SECONDS).until(
        lambda driver: driver.find_element(By.ID, "submit-button").is_enabled()
    )
    assert chrome_driver.find_element(By.ID, "refresh-history-button").is_enabled()
    assert history_items(chrome_driver)[0].is_enabled()


def test_browser_smoke_recovers_from_create_response_failure(browser_smoke_app, chrome_driver: webdriver.Chrome) -> None:
    base_url, temp_dir = browser_smoke_app
    chrome_driver.get(base_url)

    wait_for_text(chrome_driver, "#workspace-status-label", "Idle")
    WebDriverWait(chrome_driver, TEST_TIMEOUT_SECONDS).until(lambda driver: len(history_items(driver)) == 1)
    submit_clip(chrome_driver, create_dummy_clip(temp_dir, "create-fail"))

    wait_for_contains(chrome_driver, "#status", "Create-job response interrupted after submission.")
    assert_intake_controls_disabled(chrome_driver)
    assert not history_items(chrome_driver)[0].is_enabled()
    wait_for_contains(chrome_driver, "#status", "Recovered completed session")
    wait_for_verdict(chrome_driver, "ready")
    wait_for_text(chrome_driver, "#session-title", "create-fail.mp4")
    WebDriverWait(chrome_driver, TEST_TIMEOUT_SECONDS).until(
        lambda driver: driver.find_element(By.ID, "submit-button").is_enabled()
    )
    assert chrome_driver.find_element(By.ID, "refresh-history-button").is_enabled()
    assert history_items(chrome_driver)[0].is_enabled()


def test_browser_smoke_renders_structured_validation_detail(browser_smoke_app, chrome_driver: webdriver.Chrome) -> None:
    base_url, temp_dir = browser_smoke_app
    chrome_driver.get(base_url)

    wait_for_text(chrome_driver, "#workspace-status-label", "Idle")
    chrome_driver.execute_script(
        """
        const originalFetch = window.fetch.bind(window);
        window.fetch = async (url, options) => {
            if (url === '/api/analysis-jobs' && options?.method === 'POST') {
                return new Response(
                    JSON.stringify({detail: [{msg: 'Structured validation failure.'}]}),
                    {status: 422, headers: {'Content-Type': 'application/json'}}
                );
            }
            return originalFetch(url, options);
        };
        """
    )
    submit_clip(chrome_driver, create_dummy_clip(temp_dir, "validation-error"))

    wait_for_contains(chrome_driver, "#status", "Structured validation failure.")
    WebDriverWait(chrome_driver, TEST_TIMEOUT_SECONDS).until(
        lambda driver: driver.find_element(By.ID, "submit-button").is_enabled()
    )


def test_browser_smoke_unlocks_after_unrecoverable_create_response_failure(browser_smoke_app, chrome_driver: webdriver.Chrome) -> None:
    base_url, temp_dir = browser_smoke_app
    chrome_driver.get(base_url)

    wait_for_text(chrome_driver, "#workspace-status-label", "Idle")
    WebDriverWait(chrome_driver, TEST_TIMEOUT_SECONDS).until(lambda driver: len(history_items(driver)) == 1)
    chrome_driver.execute_script(
        """
        const originalFetch = window.fetch.bind(window);
        window.fetch = async (url, options) => {
            if (url === '/api/analysis-jobs' && options?.method === 'POST') {
                return new Response(
                    JSON.stringify({detail: 'Create-job response interrupted after submission.'}),
                    {status: 503, headers: {'Content-Type': 'application/json'}}
                );
            }
            return originalFetch(url, options);
        };
        """
    )
    submit_clip(chrome_driver, create_dummy_clip(temp_dir, "create-never-started"))

    wait_for_contains(chrome_driver, "#status", "Create-job response interrupted after submission.")
    assert_intake_controls_disabled(chrome_driver)
    assert not history_items(chrome_driver)[0].is_enabled()
    wait_for_contains(chrome_driver, "#status", "workspace has been unlocked")
    WebDriverWait(chrome_driver, TEST_TIMEOUT_SECONDS).until(
        lambda driver: driver.find_element(By.ID, "submit-button").is_enabled()
    )
    assert chrome_driver.find_element(By.ID, "refresh-history-button").is_enabled()
    assert history_items(chrome_driver)[0].is_enabled()


def test_browser_smoke_unlocks_after_unrecoverable_poll_failure(browser_smoke_app, chrome_driver: webdriver.Chrome) -> None:
    base_url, temp_dir = browser_smoke_app
    chrome_driver.get(base_url)

    wait_for_text(chrome_driver, "#workspace-status-label", "Idle")
    WebDriverWait(chrome_driver, TEST_TIMEOUT_SECONDS).until(lambda driver: len(history_items(driver)) == 1)
    submit_clip(chrome_driver, create_dummy_clip(temp_dir, "poll-never-recovers"))

    wait_for_contains(chrome_driver, "#status", "Temporary poll failure.")
    assert_intake_controls_disabled(chrome_driver)
    assert not history_items(chrome_driver)[0].is_enabled()
    wait_for_contains(chrome_driver, "#status", "workspace has been unlocked")
    WebDriverWait(chrome_driver, TEST_TIMEOUT_SECONDS).until(
        lambda driver: driver.find_element(By.ID, "submit-button").is_enabled()
    )
    assert chrome_driver.find_element(By.ID, "refresh-history-button").is_enabled()
    assert history_items(chrome_driver)[0].is_enabled()


def test_browser_smoke_mobile_ordering(browser_smoke_app, chrome_driver: webdriver.Chrome) -> None:
    base_url, _ = browser_smoke_app
    chrome_driver.set_window_size(390, 844)
    chrome_driver.get(base_url)

    wait_for_text(chrome_driver, "#workspace-status-label", "Idle")

    offsets = chrome_driver.execute_script(
        """
        const selectors = arguments[0];
        const offsets = {};
        for (const [key, selector] of Object.entries(selectors)) {
          const node = document.querySelector(selector);
          offsets[key] = node.getBoundingClientRect().top + window.scrollY;
        }
        return offsets;
        """,
        {
            "intake": "#intake-rail",
            "status": "#analysis-workspace .status-rail",
            "verdict": "#verdict-band",
            "frame": "#frame-stage",
            "summary": "#session-summary",
            "evidence": "#evidence-section",
            "history": "#history-shelf",
        },
    )

    ordered_sections = [
        offsets["intake"],
        offsets["status"],
        offsets["verdict"],
        offsets["frame"],
        offsets["summary"],
        offsets["evidence"],
        offsets["history"],
    ]
    assert ordered_sections == sorted(ordered_sections)
