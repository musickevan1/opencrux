const form = document.getElementById("analysis-form");
const workspaceShell = document.getElementById("analysis-workspace");
const workspaceStatusLabelNode = document.getElementById("workspace-status-label");
const statusNode = document.getElementById("status");
const sessionTitleNode = document.getElementById("session-title");
const sessionMetaNode = document.getElementById("session-meta");
const verdictBandNode = document.getElementById("verdict-band");
const verdictTitleNode = document.getElementById("verdict-title");
const verdictMessageNode = document.getElementById("verdict-message");
const warningsNode = document.getElementById("warnings");
const metricsNode = document.getElementById("metrics");
const supportingDetailsNode = document.getElementById("supporting-details");
const attemptsNode = document.getElementById("attempts");
const submitButton = document.getElementById("submit-button");
const historyEmptyNode = document.getElementById("history-empty");
const historyListNode = document.getElementById("history-list");
const refreshHistoryButton = document.getElementById("refresh-history-button");
const previewStageNode = document.getElementById("preview-stage");
const previewImageNode = document.getElementById("preview-image");
const previewEmptyNode = document.getElementById("preview-empty");
const previewProgressBarNode = document.getElementById("preview-progress-bar");
const previewProgressLabelNode = document.getElementById("preview-progress-label");
const previewFrameLabelNode = document.getElementById("preview-frame-label");
const previewScrubberNode = document.getElementById("preview-scrubber");
const previewThumbnailsNode = document.getElementById("preview-thumbnails");
const previewStatsNode = document.getElementById("preview-stats");
const llmInsightsSection = document.getElementById("llm-insights-section");
const llmModelChip = document.getElementById("llm-model-chip");
const llmSessionSummary = document.getElementById("llm-session-summary");
const llmAttemptInsights = document.getElementById("llm-attempt-insights");
const llmRecommendations = document.getElementById("llm-recommendations");

const CAUTION_WARNING_CODES = new Set([
  "low_pose_coverage",
  "low_visibility",
  "multiple_people_detected",
  "attempt_segmentation_ambiguous",
]);
const NEGATIVE_MESSAGE_PATTERNS = [/multiple climbers/i, /one dominant climber/i, /unsupported/i];
const SUBMISSION_RECOVERY_TIMEOUT_MS = 5000;
const MAX_POLL_RECOVERY_ATTEMPTS = 4;

const state = {
  activeJob: null,
  activeSession: null,
  activeSessionSource: null,
  historySessions: [],
  pendingSubmission: false,
  pendingSubmissionFilename: null,
  pollRecoveryMode: false,
  pollRecoveryStartedAt: null,
  pollRecoveryAttemptCount: 0,
  submissionRecoveryMode: false,
  submissionRecoveryStartedAt: null,
  recoveryKnownSessionIds: [],
  selectedPreviewFrameIndex: 0,
  previewFollowsLatest: true,
  statusOverride: null,
};

let activePollHandle = null;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function clearPollHandle() {
  if (activePollHandle !== null) {
    window.clearTimeout(activePollHandle);
    activePollHandle = null;
  }
}

function warningSeverity(warning) {
  return warning?.severity || "warning";
}

function severityRank(warning) {
  const severity = warningSeverity(warning);
  if (severity === "error") {
    return 2;
  }
  if (severity === "warning") {
    return 1;
  }
  return 0;
}

function sortWarnings(warnings) {
  return [...warnings].sort((left, right) => severityRank(right) - severityRank(left));
}

function metricCard(label, value, note = "") {
  return `
    <article class="metric-card">
      <div class="metric-label">${escapeHtml(label)}</div>
      <div class="metric-value">${escapeHtml(value)}</div>
      ${note ? `<div class="metric-footnote">${escapeHtml(note)}</div>` : ""}
    </article>
  `;
}

function diagnosticCard(label, value, note = "") {
  return `
    <article class="diagnostic-card">
      <div class="metric-label">${escapeHtml(label)}</div>
      <div class="metric-value">${escapeHtml(value)}</div>
      ${note ? `<div class="metric-footnote">${escapeHtml(note)}</div>` : ""}
    </article>
  `;
}

function detailRow(label, value) {
  return `
    <div class="detail-row">
      <dt class="detail-term">${escapeHtml(label)}</dt>
      <dd class="detail-value">${escapeHtml(value)}</dd>
    </div>
  `;
}

function emptyState(message) {
  return `<div class="empty-state">${escapeHtml(message)}</div>`;
}

function getErrorMessage(payload, fallback) {
  if (typeof payload?.detail === "string" && payload.detail.trim()) {
    return payload.detail;
  }

  if (Array.isArray(payload?.detail) && payload.detail.length) {
    return payload.detail
      .map((detail) => detail?.msg || detail?.message || "Request validation failed.")
      .join(" ");
  }

  return fallback;
}

function isJobActive() {
  return state.activeJob !== null && ["queued", "running"].includes(state.activeJob.status);
}

function isInteractionLocked() {
  return state.pendingSubmission || state.submissionRecoveryMode || isJobActive();
}

function getActiveFrames() {
  return state.activeJob?.preview?.frames || [];
}

function recoverSessionFromHistory() {
  let recoveryFilename = null;

  if (state.pollRecoveryMode && state.activeJob) {
    recoveryFilename = state.activeJob.original_filename;
  } else if (state.submissionRecoveryMode && state.pendingSubmissionFilename) {
    recoveryFilename = state.pendingSubmissionFilename;
  }

  if (!recoveryFilename) {
    return false;
  }

  const recoveredSession = state.historySessions.find((session) => {
    return session.original_filename === recoveryFilename && !state.recoveryKnownSessionIds.includes(session.id);
  });

  if (!recoveredSession) {
    return false;
  }

  clearPollHandle();
  state.activeJob = null;
  state.activeSession = recoveredSession;
  state.activeSessionSource = "history";
  state.pollRecoveryMode = false;
  state.pollRecoveryStartedAt = null;
  state.pollRecoveryAttemptCount = 0;
  state.submissionRecoveryMode = false;
  state.submissionRecoveryStartedAt = null;
  state.pendingSubmissionFilename = null;
  state.recoveryKnownSessionIds = [];
  state.previewFollowsLatest = true;
  state.selectedPreviewFrameIndex = 0;
  state.statusOverride = {
    message: `Recovered completed session ${recoveredSession.id} after polling was interrupted.`,
    tone: "ready",
  };
  return true;
}

function failSubmissionRecovery() {
  clearPollHandle();
  state.activeJob = null;
  state.activeSession = null;
  state.activeSessionSource = null;
  state.pendingSubmission = false;
  state.pendingSubmissionFilename = null;
  state.pollRecoveryMode = false;
  state.pollRecoveryStartedAt = null;
  state.pollRecoveryAttemptCount = 0;
  state.pollRecoveryAttemptCount = 0;
  state.submissionRecoveryMode = false;
  state.submissionRecoveryStartedAt = null;
  state.recoveryKnownSessionIds = [];
  state.statusOverride = {
    message: "Could not confirm that the submitted job started. No completed session appeared in history, so the workspace has been unlocked. Refresh history later if the result surfaces.",
    tone: "error",
  };
  renderApp();
}

function failPollRecovery() {
  clearPollHandle();
  state.activeJob = null;
  state.activeSession = null;
  state.activeSessionSource = null;
  state.pendingSubmission = false;
  state.pendingSubmissionFilename = null;
  state.pollRecoveryMode = false;
  state.pollRecoveryStartedAt = null;
  state.pollRecoveryAttemptCount = 0;
  state.statusOverride = {
    message: "Could not keep polling the analysis job, and no completed session appeared in history. The workspace has been unlocked. Refresh history later if the result surfaces.",
    tone: "error",
  };
  renderApp();
}

async function retrySubmissionRecovery() {
  if (!state.submissionRecoveryMode) {
    return;
  }

  if (Date.now() - Number(state.submissionRecoveryStartedAt || 0) > SUBMISSION_RECOVERY_TIMEOUT_MS) {
    failSubmissionRecovery();
    return;
  }

  try {
    await refreshHistory(true);
  } catch {
    renderApp();
  }

  if (!state.submissionRecoveryMode) {
    return;
  }

  renderApp();
  activePollHandle = window.setTimeout(() => {
    void retrySubmissionRecovery();
  }, 1500);
}

function formatSeconds(value) {
  return `${Number(value || 0).toFixed(2)}s`;
}

function formatRatio(value) {
  return Number(value || 0).toFixed(3);
}

function formatPercent(value) {
  return `${(Number(value || 0) * 100).toFixed(1)}%`;
}

function detectNegativeLabel(message) {
  return NEGATIVE_MESSAGE_PATTERNS.some((pattern) => pattern.test(message || ""))
    ? "Unsupported footage"
    : "Analysis failed";
}

function deriveSessionVerdict(session) {
  const warnings = sortWarnings(session?.warnings || []);
  const caution = warnings.some(
    (warning) => warningSeverity(warning) !== "info" || CAUTION_WARNING_CODES.has(warning.code),
  );
  return caution ? "caution" : "ready";
}

function deriveVerdict() {
  if (state.pendingSubmission || state.submissionRecoveryMode) {
    return {
      key: "analyzing",
      label: state.submissionRecoveryMode ? "Recovering" : "Starting",
      title: state.submissionRecoveryMode ? "Recovering submission" : "Starting analysis",
      message: state.submissionRecoveryMode
        ? "Waiting to recover the submitted job after the create response was interrupted."
        : "Creating the analysis job before live preview begins.",
    };
  }

  if (state.activeJob && ["queued", "running"].includes(state.activeJob.status)) {
    const previewWarnings = sortWarnings(state.activeJob.preview?.active_warnings || []);
    const errorWarning = previewWarnings.find((warning) => warningSeverity(warning) === "error");
    if (errorWarning) {
      return {
        key: "negative",
        label: "Negative",
        title: "Unsupported footage likely",
        message: errorWarning.message,
      };
    }

    return {
      key: "analyzing",
      label: "Analyzing",
      title: "Analyzing clip",
      message: state.activeJob.preview?.last_update_message || state.activeJob.preview?.stage || "Running local analysis.",
    };
  }

  if (state.activeJob && state.activeJob.status === "failed") {
    const message = state.activeJob.error_message || "Analysis failed.";
    return {
      key: "negative",
      label: "Negative",
      title: detectNegativeLabel(message),
      message,
    };
  }

  if (state.activeSession) {
    const warnings = sortWarnings(state.activeSession.warnings || []);
    const verdict = deriveSessionVerdict(state.activeSession);
    if (verdict === "caution") {
      return {
        key: "caution",
        label: "Caution",
        title: "Review with caution",
        message: warnings[0]?.message || "This session completed, but the reliability signals should be reviewed before trusting the metrics.",
      };
    }

    return {
      key: "ready",
      label: "Ready",
      title: "Supported run",
      message: "This session completed without reliability warnings that should block trust in the current slice.",
    };
  }

  return {
    key: "idle",
    label: "Idle",
    title: "Ready for a clip",
    message: "Upload a recorded single-climber bouldering or board session to begin the local analysis workflow.",
  };
}

function renderStatus(verdict) {
  if (state.statusOverride) {
    statusNode.textContent = state.statusOverride.message;
    statusNode.className = `status ${state.statusOverride.tone}`;
    return;
  }

  if (state.pendingSubmission || state.submissionRecoveryMode) {
    statusNode.textContent = "Creating analysis job.";
    statusNode.className = "status loading";
    return;
  }

  if (state.activeJob && ["queued", "running"].includes(state.activeJob.status)) {
    statusNode.textContent = state.activeJob.preview?.stage || "Analyzing clip locally.";
    statusNode.className = "status loading";
    return;
  }

  if (state.activeJob && state.activeJob.status === "failed") {
    statusNode.textContent = state.activeJob.error_message || "Analysis failed.";
    statusNode.className = "status error";
    return;
  }

  if (state.activeSessionSource === "job") {
    statusNode.textContent = "Analysis complete.";
    statusNode.className = "status ready";
    return;
  }

  if (state.activeSessionSource === "history" && state.activeSession) {
    statusNode.textContent = `Loaded session ${state.activeSession.id}.`;
    statusNode.className = "status idle";
    return;
  }

  statusNode.textContent = verdict.message;
  statusNode.className = `status ${verdict.key === "negative" ? "error" : verdict.key === "analyzing" ? "loading" : "idle"}`;
}

function renderWorkspaceHeader() {
  if (state.activeSession) {
    sessionTitleNode.textContent = state.activeSession.original_filename;
    sessionMetaNode.textContent = `Session ${state.activeSession.id} • ${formatSeconds(state.activeSession.source_duration_seconds)} source length • ${Number(state.activeSession.sampled_fps || 0).toFixed(2)} sampled FPS`;
    return;
  }

  if (state.pendingSubmission || state.submissionRecoveryMode) {
    sessionTitleNode.textContent = state.pendingSubmissionFilename || "Preparing clip";
    sessionMetaNode.textContent = state.submissionRecoveryMode
      ? "The workspace stays locked while OpenCrux tries to recover the submitted job from history."
      : "The workspace is locked until the create-job response resolves and live preview can begin.";
    return;
  }

  if (state.activeJob) {
    sessionTitleNode.textContent = state.activeJob.original_filename;
    sessionMetaNode.textContent = "The frame stage stays mounted while the job moves from live preview to final result.";
    return;
  }

  sessionTitleNode.textContent = "No clip selected";
  sessionMetaNode.textContent = "Upload a supported clip to mount the analysis workspace.";
}

function renderProgress() {
  if (state.pendingSubmission || state.submissionRecoveryMode) {
    previewProgressBarNode.style.width = "0%";
    previewProgressLabelNode.textContent = state.submissionRecoveryMode ? "recovering" : "starting";
    previewStageNode.textContent = state.submissionRecoveryMode
      ? "Recovering submitted job from persisted history."
      : "Creating analysis job.";
    return;
  }

  if (state.activeJob) {
    const progressRatio = Math.max(0, Math.min(state.activeJob.preview?.progress_ratio || 0, 1));
    const percent = Math.round(progressRatio * 100);
    previewProgressBarNode.style.width = `${percent}%`;
    previewProgressLabelNode.textContent = `${percent}%`;
    previewStageNode.textContent = state.activeJob.preview?.last_update_message || state.activeJob.preview?.stage || "Preparing analysis.";
    return;
  }

  if (state.activeSessionSource === "history") {
    previewProgressBarNode.style.width = "100%";
    previewProgressLabelNode.textContent = "saved";
    previewStageNode.textContent = "Stored session recall. Preview frames are not persisted in Phase 1.";
    return;
  }

  if (state.activeSessionSource === "job") {
    previewProgressBarNode.style.width = "100%";
    previewProgressLabelNode.textContent = "100%";
    previewStageNode.textContent = "Analysis complete.";
    return;
  }

  previewProgressBarNode.style.width = "0%";
  previewProgressLabelNode.textContent = "0%";
  previewStageNode.textContent = "Waiting for analysis to start.";
}

function renderPreviewFrames() {
  const frames = getActiveFrames();
  if (!frames.length) {
    previewImageNode.classList.add("hidden");
    previewEmptyNode.classList.remove("hidden");
    previewScrubberNode.disabled = true;
    previewScrubberNode.max = "0";
    previewScrubberNode.value = "0";
    previewThumbnailsNode.innerHTML = "";

    if (state.activeSessionSource === "history") {
      previewEmptyNode.textContent = "Stored sessions keep metrics and warnings, but annotated preview frames are not persisted in Phase 1.";
      previewFrameLabelNode.textContent = "Preview unavailable for stored sessions.";
    } else if (state.pendingSubmission || state.submissionRecoveryMode) {
      previewEmptyNode.textContent = "OpenCrux is creating the analysis job. Annotated MediaPipe frames will appear here as soon as processing starts.";
      previewFrameLabelNode.textContent = state.submissionRecoveryMode
        ? "Preview pending recovery from interrupted submission."
        : "Preview pending job creation.";
    } else if (state.activeJob && state.activeJob.status === "failed") {
      previewEmptyNode.textContent = "This job failed before a stable annotated frame could be retained in the workspace.";
      previewFrameLabelNode.textContent = "No preview frames retained.";
    } else if (state.activeJob) {
      previewEmptyNode.textContent = "Annotated MediaPipe frames will appear here while analysis runs.";
      previewFrameLabelNode.textContent = "No preview frames yet.";
    } else {
      previewEmptyNode.replaceChildren();
      const dropContent = document.createElement("div");
      dropContent.className = "drop-zone-content";
      const svgNS = "http://www.w3.org/2000/svg";
      const svg = document.createElementNS(svgNS, "svg");
      svg.setAttribute("class", "drop-zone-icon");
      svg.setAttribute("width", "48");
      svg.setAttribute("height", "48");
      svg.setAttribute("viewBox", "0 0 48 48");
      svg.setAttribute("fill", "none");
      svg.setAttribute("aria-hidden", "true");
      const path1 = document.createElementNS(svgNS, "path");
      path1.setAttribute("d", "M24 4L24 32M24 32L16 24M24 32L32 24");
      path1.setAttribute("stroke", "currentColor");
      path1.setAttribute("stroke-width", "2.5");
      path1.setAttribute("stroke-linecap", "round");
      path1.setAttribute("stroke-linejoin", "round");
      const path2 = document.createElementNS(svgNS, "path");
      path2.setAttribute("d", "M8 36v4a4 4 0 004 4h24a4 4 0 004-4v-4");
      path2.setAttribute("stroke", "currentColor");
      path2.setAttribute("stroke-width", "2.5");
      path2.setAttribute("stroke-linecap", "round");
      path2.setAttribute("stroke-linejoin", "round");
      svg.append(path1, path2);
      const label = document.createElement("p");
      label.className = "drop-zone-label";
      label.textContent = "Drop your send";
      const hint = document.createElement("p");
      hint.className = "drop-zone-hint";
      hint.textContent = "or tap to select a video";
      dropContent.append(svg, label, hint);
      previewEmptyNode.appendChild(dropContent);
      previewFrameLabelNode.textContent = "No preview frames yet.";
    }
    return;
  }

  const latestIndex = frames.length - 1;
  if (state.previewFollowsLatest || state.selectedPreviewFrameIndex > latestIndex) {
    state.selectedPreviewFrameIndex = latestIndex;
  }

  const selectedFrame = frames[state.selectedPreviewFrameIndex];
  previewImageNode.src = `data:image/jpeg;base64,${selectedFrame.preview_image_base64}`;
  previewImageNode.classList.remove("hidden");
  previewEmptyNode.classList.add("hidden");
  previewScrubberNode.disabled = frames.length <= 1;
  previewScrubberNode.max = String(latestIndex);
  previewScrubberNode.value = String(state.selectedPreviewFrameIndex);
  previewFrameLabelNode.textContent = `Frame ${selectedFrame.processed_frame_count} • ${selectedFrame.timestamp_seconds.toFixed(2)}s • ${selectedFrame.detected_pose_count} poses`;

  previewThumbnailsNode.innerHTML = frames
    .map(
      (frame, index) => `
        <button class="preview-thumb ${index === state.selectedPreviewFrameIndex ? "is-active" : ""}" type="button" data-preview-index="${index}">
          <img src="data:image/jpeg;base64,${frame.preview_image_base64}" alt="Preview frame at ${frame.timestamp_seconds.toFixed(2)} seconds" />
          <span>${frame.timestamp_seconds.toFixed(1)}s</span>
        </button>
      `,
    )
    .join("");

  for (const node of previewThumbnailsNode.querySelectorAll(".preview-thumb")) {
    node.addEventListener("click", () => {
      updateSelectedPreviewFrame(Number(node.dataset.previewIndex || 0));
    });
  }
}

function renderSummary() {
  if (state.activeSession?.metrics) {
    const metrics = state.activeSession.metrics;
    metricsNode.innerHTML = [
      metricCard("Attempts", metrics.attempt_count),
      metricCard("Time on wall", formatSeconds(metrics.estimated_time_on_wall_seconds)),
      metricCard("Average rest", formatSeconds(metrics.average_rest_seconds)),
      metricCard("Vertical progress", formatRatio(metrics.vertical_progress_ratio)),
      metricCard("Visibility", formatRatio(metrics.mean_pose_visibility)),
    ].join("");
    supportingDetailsNode.innerHTML = [
      detailRow("Lateral span", formatRatio(metrics.lateral_span_ratio)),
      detailRow("Hesitation markers", metrics.hesitation_marker_count),
      detailRow("Source length", formatSeconds(state.activeSession.source_duration_seconds)),
      detailRow("Sampled FPS", Number(state.activeSession.sampled_fps || 0).toFixed(2)),
    ].join("");
    return;
  }

  if (state.activeJob) {
    const preview = state.activeJob.preview || {};
    metricsNode.innerHTML = [
      metricCard("Provisional attempts", preview.provisional_attempt_count || 0),
      metricCard("Clip time", formatSeconds(preview.current_timestamp_seconds)),
      metricCard("Coverage", formatPercent(preview.coverage_ratio)),
      metricCard("Vertical progress", formatRatio(preview.provisional_vertical_progress_ratio)),
      metricCard("Visibility", formatRatio(preview.mean_pose_visibility)),
    ].join("");
    supportingDetailsNode.innerHTML = [
      detailRow("Processed frames", `${preview.processed_frame_count || 0}/${preview.total_frame_count || 0}`),
      detailRow("Visible points", preview.visible_landmark_count || 0),
      detailRow("Multi-pose rate", formatPercent(preview.multi_pose_ratio)),
      detailRow("Lateral span", formatRatio(preview.provisional_lateral_span_ratio)),
    ].join("");
    return;
  }

  metricsNode.innerHTML = [
    metricCard("Attempts", "-") ,
    metricCard("Time on wall", "-"),
    metricCard("Average rest", "-"),
    metricCard("Vertical progress", "-"),
    metricCard("Visibility", "-"),
  ].join("");
  supportingDetailsNode.innerHTML = emptyState("Metrics stay secondary until a clip is analyzed or a saved session is loaded.");
}

function renderDiagnostics() {
  if (state.pendingSubmission || state.submissionRecoveryMode) {
    previewStatsNode.innerHTML = [
      diagnosticCard("Job status", state.submissionRecoveryMode ? "recovering" : "starting"),
      diagnosticCard("Processed", "0/0"),
      diagnosticCard("Clip time", formatSeconds(0)),
      diagnosticCard("Multi-pose", formatPercent(0)),
    ].join("");
    return;
  }

  if (state.activeJob) {
    const preview = state.activeJob.preview || {};
    previewStatsNode.innerHTML = [
      diagnosticCard("Job status", state.activeJob.status),
      diagnosticCard("Processed", `${preview.processed_frame_count || 0}/${preview.total_frame_count || 0}`),
      diagnosticCard("Clip time", formatSeconds(preview.current_timestamp_seconds)),
      diagnosticCard("Multi-pose", formatPercent(preview.multi_pose_ratio)),
    ].join("");
    return;
  }

  if (state.activeSession?.metrics) {
    const metrics = state.activeSession.metrics;
    previewStatsNode.innerHTML = [
      diagnosticCard("Session status", state.activeSession.status),
      diagnosticCard("Warnings", (state.activeSession.warnings || []).length),
      diagnosticCard("Lateral span", formatRatio(metrics.lateral_span_ratio)),
      diagnosticCard("Hesitations", metrics.hesitation_marker_count),
    ].join("");
    return;
  }

  previewStatsNode.innerHTML = emptyState("Live diagnostics will appear here while a clip is processing.");
}

function renderWarnings() {
  const warnings = sortWarnings(
    state.activeJob && ["queued", "running", "failed"].includes(state.activeJob.status)
      ? state.activeJob.preview?.active_warnings || []
      : state.activeSession?.warnings || [],
  );

  if (!warnings.length) {
    const message = state.activeSession
      ? "No reliability warnings were raised for this session."
      : state.activeJob
        ? "No reliability warnings have fired yet."
        : "Warnings will appear here when reliability drops or footage is unsupported.";
    warningsNode.innerHTML = emptyState(message);
    return;
  }

  warningsNode.innerHTML = warnings
    .map(
      (warning) => `
        <article class="warning ${escapeHtml(warningSeverity(warning))}">
          <strong>${escapeHtml(warning.code)}</strong>
          <p>${escapeHtml(warning.message)}</p>
        </article>
      `,
    )
    .join("");
}

function renderAttempts() {
  const attempts = state.activeJob && ["queued", "running", "failed"].includes(state.activeJob.status)
    ? state.activeJob.preview?.provisional_attempts || []
    : state.activeSession?.attempts || [];

  if (!attempts.length) {
    const message = state.activeJob
      ? "No provisional attempt window yet."
      : state.activeSession
        ? "No attempts were persisted for this session."
        : "Attempts and timing evidence will appear here after analysis begins.";
    attemptsNode.innerHTML = emptyState(message);
    return;
  }

  attemptsNode.innerHTML = attempts
    .map((attempt) => {
      const hesitationText = Array.isArray(attempt.hesitation_markers) && attempt.hesitation_markers.length
        ? attempt.hesitation_markers
            .map((marker) => `${Number(marker.timestamp_seconds).toFixed(2)}s (${Number(marker.duration_seconds).toFixed(2)}s)`)
            .join(", ")
        : "None";
      const hasDerivedMetrics = typeof attempt.vertical_progress_ratio === "number" && typeof attempt.lateral_span_ratio === "number";

      return `
        <article class="attempt-card">
          <h4>${escapeHtml(hasDerivedMetrics ? `Attempt ${attempt.index}` : `Provisional attempt ${attempt.index}`)}</h4>
          <p>Window: ${Number(attempt.start_seconds).toFixed(2)}s to ${Number(attempt.end_seconds).toFixed(2)}s</p>
          <p>Duration: ${Number(attempt.duration_seconds).toFixed(2)}s</p>
          ${hasDerivedMetrics ? `<p>Vertical progress: ${Number(attempt.vertical_progress_ratio).toFixed(3)}</p>` : ""}
          ${hasDerivedMetrics ? `<p>Lateral span: ${Number(attempt.lateral_span_ratio).toFixed(3)}</p>` : ""}
          ${hasDerivedMetrics ? `<p>Hesitation markers: ${escapeHtml(hesitationText)}</p>` : ""}
        </article>
      `;
    })
    .join("");
}

function renderLLMInsights() {
  const insights = state.activeSession?.llm_insights;

  if (!insights || !insights.attempt_insights?.length) {
    // Show placeholder instead of hiding — lets users know the feature exists
    llmInsightsSection.classList.remove("hidden");
    llmModelChip.textContent = "disabled";
    llmSessionSummary.innerHTML = "";
    llmAttemptInsights.innerHTML = "";
    llmRecommendations.innerHTML = "";

    llmAttemptInsights.innerHTML = `
      <div class="llm-placeholder" style="grid-column: 1 / -1;">
        <p class="llm-placeholder-title">Gemma AI insights not enabled</p>
        <p>Install the LLM extra and enable Gemma 4 to get technique scoring, movement descriptions, and coaching tips.</p>
        <p style="margin-top: 10px;"><code>pip install -e ".[llm]"</code> then set <code>OPENCRUX_GEMMA_ENABLED=true</code></p>
        <div class="llm-features">
          <span class="llm-feature-chip">Technique scores</span>
          <span class="llm-feature-chip">Movement descriptions</span>
          <span class="llm-feature-chip">Coaching tips</span>
          <span class="llm-feature-chip">Difficulty estimates</span>
          <span class="llm-feature-chip">Session summary</span>
        </div>
      </div>
    `;
    return;
  }

  llmInsightsSection.classList.remove("hidden");

  // Model chip
  const modelShort = insights.model_variant.split("/").pop() || insights.model_variant;
  llmModelChip.textContent = modelShort;

  // Session summary
  if (insights.session_summary) {
    llmSessionSummary.innerHTML = `
      <div class="llm-summary-block">
        <p>${escapeHtml(insights.session_summary)}</p>
      </div>
    `;
  } else {
    llmSessionSummary.innerHTML = "";
  }

  // Attempt insights
  llmAttemptInsights.innerHTML = insights.attempt_insights
    .map((insight) => {
      const scores = insight.technique_scores;
      const overall = scores ? scores.overall : null;
      const tips = insight.coaching_tips || [];

      return `
        <article class="llm-attempt-card">
          <div class="llm-attempt-header">
            <h4>Attempt ${insight.attempt_index}</h4>
            ${overall !== null ? `<span class="llm-overall-score">${overall.toFixed(1)}/5.0</span>` : ""}
          </div>
          ${insight.movement_description ? `<p class="llm-movement-desc">${escapeHtml(insight.movement_description)}</p>` : ""}
          ${scores ? `
            <div class="llm-scores-grid">
              <div class="llm-score-item">
                <span class="llm-score-label">Footwork</span>
                <span class="llm-score-value">${scores.footwork.toFixed(1)}</span>
              </div>
              <div class="llm-score-item">
                <span class="llm-score-label">Body tension</span>
                <span class="llm-score-value">${scores.body_tension.toFixed(1)}</span>
              </div>
              <div class="llm-score-item">
                <span class="llm-score-label">Route reading</span>
                <span class="llm-score-value">${scores.route_reading.toFixed(1)}</span>
              </div>
              <div class="llm-score-item">
                <span class="llm-score-label">Efficiency</span>
                <span class="llm-score-value">${scores.efficiency.toFixed(1)}</span>
              </div>
            </div>
          ` : ""}
          ${insight.difficulty_estimate ? `<p class="llm-difficulty">Est. grade: ${escapeHtml(insight.difficulty_estimate)}</p>` : ""}
          ${tips.length ? `
            <div class="llm-tips">
              <h5>Coaching tips</h5>
              <ul>
                ${tips.map((tip) => `<li>${escapeHtml(tip)}</li>`).join("")}
              </ul>
            </div>
          ` : ""}
          ${typeof insight.confidence === "number" ? `<p class="llm-confidence">Confidence: ${(insight.confidence * 100).toFixed(0)}%</p>` : ""}
        </article>
      `;
    })
    .join("");

  // Recommendations
  const recs = insights.overall_recommendations || [];
  if (recs.length) {
    llmRecommendations.innerHTML = `
      <div class="llm-recs-block">
        <h4>Recommendations</h4>
        <ul>
          ${recs.map((rec) => `<li>${escapeHtml(rec)}</li>`).join("")}
        </ul>
      </div>
    `;
  } else {
    llmRecommendations.innerHTML = "";
  }
}

function deriveHistoryPosture(session) {
  return deriveSessionVerdict(session) === "caution" ? "caution" : "ready";
}

function renderHistory() {
  historyListNode.innerHTML = "";
  if (!state.historySessions.length) {
    historyEmptyNode.classList.remove("hidden");
    return;
  }

  historyEmptyNode.classList.add("hidden");
  const disableHistory = isInteractionLocked();
  historyListNode.innerHTML = state.historySessions
    .map((session) => {
      const posture = deriveHistoryPosture(session);
      return `
        <button class="history-item ${posture === "caution" ? "is-caution" : ""}" type="button" data-session-id="${escapeHtml(session.id)}" ${disableHistory ? "disabled" : ""}>
          <div class="history-item-head">
            <strong>${escapeHtml(session.original_filename)}</strong>
            <span class="history-chip ${escapeHtml(posture)}">${escapeHtml(posture)}</span>
          </div>
          <div class="history-item-body">
            <p class="history-meta">${escapeHtml(session.status)} • ${escapeHtml(String(session.attempts.length))} attempts</p>
            <p class="history-submeta">${escapeHtml(formatSeconds(session.source_duration_seconds))} source length • ${(session.warnings || []).length} warnings</p>
          </div>
        </button>
      `;
    })
    .join("");

  for (const node of historyListNode.querySelectorAll(".history-item")) {
    node.addEventListener("click", async () => {
      if (isInteractionLocked()) {
        return;
      }
      await loadHistorySession(node.dataset.sessionId || "");
    });
  }
}

function updateControls() {
  const disableInteractions = isInteractionLocked();
  for (const element of form.elements) {
    element.disabled = disableInteractions;
  }
  refreshHistoryButton.disabled = disableInteractions;
}

function verdictIconSvg(key) {
  const icons = {
    idle: '<svg class="verdict-icon" viewBox="0 0 24 24" fill="none"><path d="M12 3a5 5 0 014.9 4.03A4.5 4.5 0 0118.5 16H12m0-13a5 5 0 00-4.9 4.03A4.5 4.5 0 005.5 16H12m0-13v13m0 0v5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
    ready: '<svg class="verdict-icon" viewBox="0 0 24 24" fill="none"><path d="M9 12l2 2 4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5"/></svg>',
    caution: '<svg class="verdict-icon" viewBox="0 0 24 24" fill="none"><path d="M12 9v4m0 3h.01M12 3L2 21h20L12 3z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    analyzing: '<svg class="verdict-icon verdict-icon-spin" viewBox="0 0 24 24" fill="none"><path d="M12 2v4m0 12v4m-7.07-3.93l2.83-2.83m8.48-8.48l2.83-2.83M2 12h4m12 0h4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
    negative: '<svg class="verdict-icon" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5"/><path d="M15 9l-6 6m0-6l6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  };
  return icons[key] || icons.idle;
}

function renderVerdict() {
  const verdict = deriveVerdict();
  workspaceShell.dataset.verdict = verdict.key;
  workspaceShell.className = `workspace-shell verdict-${verdict.key}`;
  verdictBandNode.className = `verdict-band verdict-${verdict.key}`;
  verdictTitleNode.textContent = verdict.title;
  verdictMessageNode.textContent = verdict.message;
  workspaceStatusLabelNode.textContent = verdict.label;

  const existingIcon = verdictTitleNode.parentElement.querySelector(".verdict-icon");
  if (existingIcon) existingIcon.remove();
  verdictTitleNode.insertAdjacentHTML("beforebegin", verdictIconSvg(verdict.key));

  renderStatus(verdict);
}

function renderApp() {
  renderWorkspaceHeader();
  renderVerdict();
  renderProgress();
  renderPreviewFrames();
  renderDiagnostics();
  renderWarnings();
  renderAttempts();
  renderSummary();
  renderLLMInsights();
  renderHistory();
  updateControls();
}

function updateSelectedPreviewFrame(index) {
  const frames = getActiveFrames();
  if (!frames.length) {
    return;
  }

  const clampedIndex = Math.max(0, Math.min(index, frames.length - 1));
  state.selectedPreviewFrameIndex = clampedIndex;
  state.previewFollowsLatest = clampedIndex === frames.length - 1;
  renderApp();
}

async function pollJob(jobId) {
  try {
    const response = await fetch(`/api/analysis-jobs/${jobId}`);
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(getErrorMessage(payload, "Could not keep polling the analysis job. Refresh history to recover the latest completed session."));
    }

    state.activeJob = payload;
    state.pendingSubmission = false;
    state.pendingSubmissionFilename = null;
    state.pollRecoveryMode = false;
    state.pollRecoveryStartedAt = null;
    state.pollRecoveryAttemptCount = 0;
    state.submissionRecoveryMode = false;
    state.submissionRecoveryStartedAt = null;
    state.statusOverride = null;
    if (payload.status === "completed" && payload.result) {
      clearPollHandle();
      state.activeSession = payload.result;
      state.activeSessionSource = "job";
      await refreshHistory(true);
      renderApp();
      return;
    }

    if (payload.status === "failed") {
      clearPollHandle();
      state.activeSession = null;
      state.activeSessionSource = null;
      renderApp();
      return;
    }

    renderApp();
    activePollHandle = window.setTimeout(() => {
      void pollJob(jobId);
    }, 850);
  } catch (error) {
    clearPollHandle();
    state.pendingSubmission = false;
    state.pendingSubmissionFilename = null;
    state.pollRecoveryMode = true;
    state.pollRecoveryStartedAt = state.pollRecoveryStartedAt || Date.now();
    state.pollRecoveryAttemptCount += 1;
    state.statusOverride = {
      message: error instanceof Error
        ? error.message
        : "Could not keep polling the analysis job. Retrying while the workspace stays locked.",
      tone: "error",
    };
    try {
      await refreshHistory(true);
    } catch {
      renderApp();
    }
    if (state.pollRecoveryAttemptCount >= MAX_POLL_RECOVERY_ATTEMPTS) {
      failPollRecovery();
      return;
    }
    if (!state.activeJob) {
      return;
    }
    renderApp();
    activePollHandle = window.setTimeout(() => {
      void pollJob(jobId);
    }, 1500);
  }
}

async function refreshHistory(silent = false) {
  const response = await fetch("/api/sessions?limit=12");
  const payload = await response.json();
  if (!response.ok) {
    if (!silent) {
      state.statusOverride = {
        message: getErrorMessage(payload, "Could not load recent sessions."),
        tone: "error",
      };
      renderApp();
    }
    return;
  }

  state.historySessions = payload;
  if (recoverSessionFromHistory()) {
    renderApp();
    return;
  }

  if (!silent) {
    state.statusOverride = null;
  }
  renderApp();
}

async function loadHistorySession(sessionId) {
  if (isInteractionLocked()) {
    return;
  }

  const response = await fetch(`/api/sessions/${sessionId}`);
  const payload = await response.json();
  if (!response.ok) {
    state.statusOverride = {
      message: getErrorMessage(payload, "Could not load that session."),
      tone: "error",
    };
    renderApp();
    return;
  }

  clearPollHandle();
  state.activeJob = null;
  state.activeSession = payload;
  state.activeSessionSource = "history";
  state.pollRecoveryMode = false;
  state.pollRecoveryStartedAt = null;
  state.pollRecoveryAttemptCount = 0;
  state.submissionRecoveryMode = false;
  state.submissionRecoveryStartedAt = null;
  state.recoveryKnownSessionIds = [];
  state.previewFollowsLatest = true;
  state.selectedPreviewFrameIndex = 0;
  state.statusOverride = null;
  renderApp();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (isInteractionLocked()) {
    return;
  }

  const submission = new FormData(form);
  const selectedFile = submission.get("file");
  const submissionStartedAt = Date.now();

  clearPollHandle();
  state.pendingSubmission = true;
  state.pendingSubmissionFilename = selectedFile instanceof File ? selectedFile.name : "Preparing clip";
  state.activeJob = null;
  state.activeSession = null;
  state.activeSessionSource = null;
  state.pollRecoveryMode = false;
  state.pollRecoveryStartedAt = null;
  state.pollRecoveryAttemptCount = 0;
  state.submissionRecoveryMode = false;
  state.submissionRecoveryStartedAt = null;
  state.recoveryKnownSessionIds = state.historySessions.map((session) => session.id);
  state.selectedPreviewFrameIndex = 0;
  state.previewFollowsLatest = true;
  state.statusOverride = null;
  renderApp();

  let response;
  try {
    response = await fetch("/api/analysis-jobs", {
      method: "POST",
      body: submission,
    });
    const payload = await response.json();
    if (!response.ok) {
      if (response.status >= 500) {
        throw new Error(getErrorMessage(payload, "Create-job response was interrupted after submission. Recovering from history."));
      }
      throw new Error(getErrorMessage(payload, "Analysis failed."));
    }

    state.pendingSubmission = false;
    state.pendingSubmissionFilename = null;
    state.activeJob = payload;
    state.statusOverride = null;
    renderApp();
    void pollJob(payload.id);
  } catch (error) {
    const ambiguousCreateFailure = !response || response.status >= 500;
    if (ambiguousCreateFailure) {
      clearPollHandle();
      state.pendingSubmission = false;
      state.submissionRecoveryMode = true;
      state.submissionRecoveryStartedAt = submissionStartedAt;
      state.statusOverride = {
        message: error instanceof Error
          ? error.message
          : "Create-job response was interrupted after submission. Recovering from history.",
        tone: "error",
      };
      try {
        await refreshHistory(true);
      } catch {
        renderApp();
      }
      if (!state.submissionRecoveryMode) {
        return;
      }
      renderApp();
      activePollHandle = window.setTimeout(async () => {
        await retrySubmissionRecovery();
      }, 1500);
      return;
    }

    state.pendingSubmission = false;
    state.pendingSubmissionFilename = null;
    state.activeJob = null;
    state.statusOverride = {
      message: error instanceof Error ? error.message : "Analysis failed.",
      tone: "error",
    };
    renderApp();
  }
});

refreshHistoryButton.addEventListener("click", async () => {
  if (isInteractionLocked()) {
    return;
  }
  await refreshHistory();
});

previewScrubberNode.addEventListener("input", () => {
  updateSelectedPreviewFrame(Number(previewScrubberNode.value));
});

/* ============================================================
   Drag-and-Drop Upload
   ============================================================ */

const frameStage = document.getElementById("frame-stage");
const videoFileInput = document.getElementById("video-file");

function preventDefaults(event) {
  event.preventDefault();
  event.stopPropagation();
}

["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
  frameStage.addEventListener(eventName, preventDefaults);
  document.body.addEventListener(eventName, preventDefaults);
});

["dragenter", "dragover"].forEach((eventName) => {
  frameStage.addEventListener(eventName, () => {
    if (!isInteractionLocked()) {
      frameStage.classList.add("drag-over");
    }
  });
});

["dragleave", "drop"].forEach((eventName) => {
  frameStage.addEventListener(eventName, () => {
    frameStage.classList.remove("drag-over");
  });
});

frameStage.addEventListener("drop", (event) => {
  if (isInteractionLocked()) {
    return;
  }
  const files = event.dataTransfer?.files;
  if (files && files.length > 0) {
    const file = files[0];
    if (file.type.startsWith("video/")) {
      videoFileInput.files = files;
      videoFileInput.dispatchEvent(new Event("change", { bubbles: true }));
      form.requestSubmit();
    }
  }
});

frameStage.addEventListener("click", () => {
  if (!isInteractionLocked() && previewEmptyNode && !previewEmptyNode.classList.contains("hidden")) {
    videoFileInput.click();
  }
});

/* ============================================================
   Theme Switcher
   ============================================================ */

const themeSelect = document.getElementById("theme-select");
if (themeSelect) {
  // Set initial value from URL or localStorage
  const currentTheme = new URLSearchParams(window.location.search).get("theme") || localStorage.getItem("opencrux-theme") || "";
  themeSelect.value = currentTheme;

  themeSelect.addEventListener("change", () => {
    const theme = themeSelect.value;
    if (theme) {
      localStorage.setItem("opencrux-theme", theme);
      // Reload with theme query param
      const url = new URL(window.location);
      url.searchParams.set("theme", theme);
      window.location.href = url.toString();
    } else {
      localStorage.removeItem("opencrux-theme");
      // Reload without theme
      const url = new URL(window.location);
      url.searchParams.delete("theme");
      window.location.href = url.toString();
    }
  });
}

renderApp();
void refreshHistory(true);
