# syntax=docker/dockerfile:1

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first so application edits do not invalidate the layer.
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --requirement requirements.txt

COPY app ./app
COPY templates ./templates

# Generated workspaces are bind-mounted from a named volume at runtime.
# GENERATED_DIR must point outside the image so artifacts survive redeploys.
ENV GENERATED_DIR=/var/lib/aladdin/generated
RUN mkdir -p "$GENERATED_DIR" \
    && useradd --create-home --uid 10001 aladdin \
    && chown -R aladdin:aladdin /app "$GENERATED_DIR"

USER aladdin

EXPOSE 8000

# Overridden by the worker service in deploy/compose.yml.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
