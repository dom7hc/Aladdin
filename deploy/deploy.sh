#!/bin/sh
# Deploy one environment's stack on the shared VM.
#
# Invoked through `az vm run-command invoke --scripts @deploy/deploy.sh`,
# which passes --parameters as positional arguments. Never run over SSH.
#
# Checks out the exact deployed revision so deploy/compose.yml always
# matches the images being started.
set -eu

IMAGE_TAG="$1"
DEPLOY_ENV="$2"
COMPOSE_PROJECT_NAME="$3"
MONGO_DATABASE="$4"
PUBLIC_PORT="$5"

ENV_DIR="/opt/aladdin/$DEPLOY_ENV"
RELEASE_DIR="/opt/aladdin/releases/$IMAGE_TAG"
REPOSITORY_DIR="/opt/aladdin/repository"
RELEASES_DIR="/opt/aladdin/releases"

if [ ! -f "$ENV_DIR/runtime.env" ]; then
  echo "Missing $ENV_DIR/runtime.env; run the VM bootstrap first" >&2
  exit 1
fi

# Serialize development and production deployments: Azure VM Run Command
# allows one active script, and both environments share this host.
exec 9>/var/lock/aladdin-deploy.lock
flock 9

# --- Resolve the release revision ------------------------------------------

if [ ! -d "$REPOSITORY_DIR/.git" ]; then
  git clone --filter=blob:none https://github.com/dom7hc/Aladdin.git "$REPOSITORY_DIR"
fi

git -C "$REPOSITORY_DIR" fetch --prune origin "+refs/heads/*:refs/remotes/origin/*"
git -C "$REPOSITORY_DIR" cat-file -e "$IMAGE_TAG^{commit}"
if [ ! -d "$RELEASE_DIR" ]; then
  git -C "$REPOSITORY_DIR" worktree add --detach "$RELEASE_DIR" "$IMAGE_TAG"
fi

cat >"$ENV_DIR/release.env.new" <<EOF
IMAGE_TAG=$IMAGE_TAG
DEPLOY_ENV=$DEPLOY_ENV
COMPOSE_PROJECT_NAME=$COMPOSE_PROJECT_NAME
MONGO_DATABASE=$MONGO_DATABASE
PUBLIC_PORT=$PUBLIC_PORT
EOF

# --- Helpers ----------------------------------------------------------------

# Runs compose for whichever release the given env file names, so rollback
# can drive the previous release's compose.yml rather than this one's.
compose_for() {
  release_env="$1"
  shift
  release_tag="$(sed -n 's/^IMAGE_TAG=//p' "$release_env")"
  release_path="$RELEASES_DIR/$release_tag"

  docker compose \
    --project-name "$COMPOSE_PROJECT_NAME" \
    --env-file "$ENV_DIR/runtime.env" \
    --env-file "$release_env" \
    --file "$release_path/deploy/compose.yml" \
    "$@"
}

check_health() {
  curl --fail --silent --show-error \
    --retry 12 --retry-delay 5 --retry-all-errors \
    "http://127.0.0.1:$PUBLIC_PORT/health"
}

rollback() {
  compose_for "$ENV_DIR/release.env.new" logs --no-color --tail 200 || true

  if [ -f "$ENV_DIR/current.env" ]; then
    compose_for "$ENV_DIR/current.env" pull
    compose_for "$ENV_DIR/current.env" up -d --remove-orphans
    if ! check_health; then
      compose_for "$ENV_DIR/current.env" logs --no-color --tail 200 || true
      echo "Deployment and rollback health checks failed" >&2
      exit 2
    fi
    echo "Deployment failed; previous release restored" >&2
    exit 1
  fi

  # A first deployment has no previous release. Remove the unhealthy stack.
  compose_for "$ENV_DIR/release.env.new" down --remove-orphans || true
  echo "First deployment failed; no previous release exists" >&2
  exit 1
}

# Keep the five most recent worktrees so the disk cannot fill and block
# future deployments. Releases still referenced by current/previous are
# among the newest, so this never removes a rollback target.
prune_releases() {
  keep=5
  ls -1dt "$RELEASES_DIR"/*/ 2>/dev/null | tail -n "+$((keep + 1))" | while read -r stale; do
    git -C "$REPOSITORY_DIR" worktree remove --force "${stale%/}" 2>/dev/null || true
  done
  git -C "$REPOSITORY_DIR" worktree prune || true

  # Every deployment pulls two new commit-tagged images, so without this the
  # 30 GB OS disk fills and future deployments fail. Only images unused for a
  # week go: images in use are untouched, and the rollback target is far
  # newer than the cutoff.
  docker image prune --all --force --filter "until=168h" >/dev/null 2>&1 || true
}

# --- Deploy -----------------------------------------------------------------

AZURE_REGISTRY="$(sed -n 's/^AZURE_REGISTRY=//p' "$ENV_DIR/runtime.env")"
az login --identity --output none
az acr login --name "$AZURE_REGISTRY" --output none

if ! compose_for "$ENV_DIR/release.env.new" pull; then
  echo "Image pull failed; active release was not changed" >&2
  exit 1
fi

if ! compose_for "$ENV_DIR/release.env.new" up -d --remove-orphans; then
  rollback
fi

if check_health; then
  if [ -f "$ENV_DIR/current.env" ]; then
    cp "$ENV_DIR/current.env" "$ENV_DIR/previous.env"
  fi
  mv "$ENV_DIR/release.env.new" "$ENV_DIR/current.env"
  compose_for "$ENV_DIR/current.env" ps
  prune_releases
  echo "Deployed $IMAGE_TAG to $DEPLOY_ENV on port $PUBLIC_PORT"
  exit 0
fi

rollback
