FROM python:3.12-slim

# System deps for OpenCV headless and MediaPipe
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxrender1 libxext6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy everything needed for install
COPY pyproject.toml README.md ./
COPY src/ src/

# Install as regular package (not editable)
RUN pip install --no-cache-dir ".[llm]"

# Pre-download the MediaPipe pose model at build time
RUN python -c "from opencrux.config import get_settings; from opencrux.analysis import ensure_pose_model_file; ensure_pose_model_file(get_settings())"

# Create data dirs
RUN mkdir -p data/models data/uploads data/sessions

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "opencrux.main:app", "--host", "0.0.0.0", "--port", "8000"]
