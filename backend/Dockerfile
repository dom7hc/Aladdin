# syntax=docker/dockerfile:1

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Docker CLI + compose plugin: the preview feature builds and runs generated
# PoCs against the host daemon through the mounted /var/run/docker.sock.
# Without the socket the preview endpoints degrade to a clear 503/409.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg \
       | gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian bookworm stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-cli docker-compose-plugin \
    && apt-get purge -y gnupg \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first so application edits do not invalidate the layer.
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --requirement requirements.txt

COPY app ./app
COPY templates ./templates

# Generated workspaces are bind-mounted from a named volume at runtime.
# GENERATED_DIR must point outside the image so artifacts survive redeploys.
ENV GENERATED_DIR=/var/lib/aladdin/generated
# Access to the host's Docker socket is granted at runtime via group_add in
# deploy/compose.yml, not baked in here: the gid differs per host, and a
# hardcoded 999 silently mismatched the deployment VM's docker group (114).
RUN mkdir -p "$GENERATED_DIR" \
    && useradd --create-home --uid 10001 aladdin \
    && chown -R aladdin:aladdin /app "$GENERATED_DIR"

USER aladdin

EXPOSE 8000

# Overridden by the worker service in deploy/compose.yml.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
