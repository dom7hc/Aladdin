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
# Created empty if absent, never overwritten. AZURE_REGISTRY is read by both
# deploy.sh (for `az acr login`) and compose.yml (to resolve image names).
# LLM credentials belong here too once the stub agents are replaced.

for env_name in development production; do
  env_file="/opt/aladdin/$env_name/runtime.env"
  if [ ! -f "$env_file" ]; then
    install -o root -g root -m 0600 /dev/null "$env_file"
    printf 'AZURE_REGISTRY=%s\n' "$REGISTRY" >"$env_file"
    echo "Created $env_file" >&2
  else
    echo "$env_file exists; leaving it unchanged" >&2
  fi
  chmod 0600 "$env_file"
  chown root:root "$env_file"
done

# --- Verification -----------------------------------------------------------

docker version --format 'Docker {{.Server.Version}}'
docker compose version
git --version
az version --output tsv --query '"azure-cli"'
az login --identity --output none
az acr login --name "$REGISTRY" --output none
echo "Bootstrap complete; ACR login to $REGISTRY succeeded"
