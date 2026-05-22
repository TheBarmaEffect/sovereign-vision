# Sovereign Vision — Docker image for the simulation / CI backend.
#
# Note: MLX is Apple-Silicon-only, so this image runs the constitutional
# firewall on the simulation backend. Useful for CI, integration tests,
# and headless deployment in environments where you only need the
# certificate stream (not real inference).
#
# On Apple Silicon, run natively in a venv instead — MLX gives you ~55+
# FPS on yolo26m and is the recommended deployment target.

FROM python:3.12-slim

LABEL org.opencontainers.image.title="Sovereign Vision"
LABEL org.opencontainers.image.description="On-device constitutional CV firewall"
LABEL org.opencontainers.image.licenses="AGPL-3.0"
LABEL org.opencontainers.image.source="https://github.com/TheBarmaEffect/sovereign-vision"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# OpenCV needs libGL etc. opencv-python-headless avoids the X11 deps
# but still requires libglib for some submodules.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml setup.py requirements.txt ./
RUN pip install --no-cache-dir \
    numpy "opencv-python-headless>=4.10" rich pydantic structlog PyYAML

COPY sovereign ./sovereign
COPY dashboard ./dashboard
COPY demo ./demo
COPY benchmarks ./benchmarks
COPY configs ./configs

RUN pip install --no-cache-dir -e .

# default command: run a 200-frame headless demo to produce a session cert.
ENTRYPOINT ["python", "-m", "demo.run_demo"]
CMD ["--headless", "--max-frames", "200", "--output-dir", "/data/certificates"]

VOLUME ["/data"]
