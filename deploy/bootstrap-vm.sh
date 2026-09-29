#!/usr/bin/env bash
# One-time (idempotent) host preparation for the shared deployment VM.
#
# Run through Azure VM Run Command or an approved SSH session:
#   az vm run-command invoke -g Need4Sleep -n n4sServer \
#     --command-id RunShellScript --scripts @deploy/bootstrap-vm.sh
#
# Creates no secrets. runtime.env is created empty and root-only; populate
# it afterwards with sudoedit so values never enter logs or shell history.
set -euo pipefail

REGISTRY="${1:-n4sacr}"

# --- Packages ---------------------------------------------------------------
# Docker, Compose, Git and the Azure CLI are already present on n4sServer;
# this only installs what is missing, so re-running is safe.

need() { ! command -v "$1" >/dev/null 2>&1; }

if need docker || need git || need az; then
  echo "Installing missing prerequisites" >&2
  apt-get update
  apt-get install -y ca-certificates curl git gnupg

  if need docker; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
      | gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    . /etc/os-release
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
      >/etc/apt/sources.list.d/docker.list

    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io \
      docker-buildx-plugin docker-compose-plugin
  fi

  if need az; then
    curl -sL https://aka.ms/InstallAzureCLIDeb | bash
  fi
fi

# --- Directories ------------------------------------------------------------

install -d -m 0750 /opt/aladdin
install -d -m 0750 /opt/aladdin/development
install -d -m 0750 /opt/aladdin/production
install -d -m 0750 /opt/aladdin/releases

# --- Log rotation -----------------------------------------------------------
# Without this, container logs can fill the 30 GB OS disk and wedge deploys.

if [ ! -f /etc/docker/daemon.json ]; then
  install -d -m 0755 /etc/docker
  cat >/etc/docker/daemon.json <<'JSON'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
JSON
  systemctl restart docker
else
  echo "/etc/docker/daemon.json exists; leaving it unchanged" >&2
fi

# Survive reboots.
systemctl enable docker

# --- Runtime environment files ----------------------------------------------
# Created with a template if absent, never overwritten.
#
#   AZURE_REGISTRY  read by deploy.sh (az acr login) and compose.yml (images)
#   MONGODB_URI     managed Cosmos DB for MongoDB vCore cluster; carries
#                   credentials, so it is filled in by hand and never committed
#
# LLM credentials belong here too once the stub agents are replaced.

for env_name in development production; do
  env_file="/opt/aladdin/$env_name/runtime.env"
  if [ ! -f "$env_file" ]; then
    install -o root -g root -m 0600 /dev/null "$env_file"
    cat >"$env_file" <<TEMPLATE
AZURE_REGISTRY=$REGISTRY
# Required: deployments fail until this is set. Add the administrator
# password, then uncomment. Percent-encode any of @ / : ? # & % in it.
# MONGODB_URI=mongodb+srv://dbuser5fjdrl:PASSWORD@n4s-docdb-cluster.mongocluster.cosmos.azure.com/?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000
TEMPLATE
    echo "Created $env_file -- set MONGODB_URI before deploying" >&2
  else
    echo "$env_file exists; leaving it unchanged" >&2
  fi
  chmod 0600 "$env_file"
  chown root:root "$env_file"

  if ! grep -q '^MONGODB_URI=' "$env_file"; then
    echo "WARNING: MONGODB_URI unset in $env_file; deployments will fail" >&2
  fi
done

# --- Reverse proxy ----------------------------------------------------------
# Caddy terminates TLS for both environments and is deliberately outside the
# per-environment deploy path, so an application deployment cannot take it
# down. Started from the checked-out repository if one is present; on a fresh
# VM the first deployment clones it and this becomes a no-op re-run.

REPOSITORY_DIR="/opt/aladdin/repository"
CADDY_DIR="$REPOSITORY_DIR/deploy/caddy"

if [ -d "$REPOSITORY_DIR/.git" ]; then
  # deploy.sh only fetches; it builds worktrees and never moves this working
  # tree, so refresh it here or the proxy config would stay at clone time.
  git -C "$REPOSITORY_DIR" fetch --prune origin "+refs/heads/*:refs/remotes/origin/*"
  git -C "$REPOSITORY_DIR" checkout --force --detach origin/main
fi

if [ -d "$CADDY_DIR" ]; then
  docker compose --project-name aladdin-proxy --file "$CADDY_DIR/compose.yml" up -d
else
  echo "No proxy config on origin/main yet; start the proxy once it lands" >&2
fi

# --- Verification -----------------------------------------------------------

docker version --format 'Docker {{.Server.Version}}'
docker compose version
git --version
az version --output tsv --query '"azure-cli"'
az login --identity --output none
az acr login --name "$REGISTRY" --output none
echo "Bootstrap complete; ACR login to $REGISTRY succeeded"
