# FINAUDIT AI API + worker image (same image, different command).
# Override for a registry mirror, e.g. --build-arg PYTHON_IMAGE=mirror.gcr.io/library/python:3.12-slim
ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE} AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# No apt packages needed: Docling pulls opencv-python-headless, and torch bundles libgomp.

WORKDIR /app

# CPU-only torch keeps the image ~2 GB smaller than the default CUDA wheels.
# Override with --build-arg TORCH_INDEX_URL=https://pypi.org/simple if download.pytorch.org is unreachable.
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
RUN pip install --index-url "${TORCH_INDEX_URL}" torch torchvision

COPY pyproject.toml ./
COPY app ./app
ARG INSTALL_DEV=false
RUN if [ "$INSTALL_DEV" = "true" ]; then pip install ".[dev]"; else pip install .; fi

# Pre-download Docling layout + TableFormer (+ figure classifier) weights so containers run offline.
# Set --build-arg DOCLING_PRELOAD_MODELS=false to skip: the directory stays empty, the app ignores it,
# and Docling downloads weights from HuggingFace on first use instead.
ARG DOCLING_PRELOAD_MODELS=true
ENV FINAUDIT_DOCLING_ARTIFACTS_PATH=/opt/docling-models
RUN mkdir -p "$FINAUDIT_DOCLING_ARTIFACTS_PATH" && if [ "$DOCLING_PRELOAD_MODELS" = "true" ]; then \
      docling-tools models download layout tableformer picture_classifier -o "$FINAUDIT_DOCLING_ARTIFACTS_PATH"; fi

COPY tests ./tests

RUN useradd --create-home --uid 1000 finaudit && mkdir -p /data && chown finaudit /data
USER finaudit

ENV FINAUDIT_DATA_DIR=/data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/v1/health', timeout=4).status == 200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
