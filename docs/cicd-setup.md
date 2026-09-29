# Aladdin CI/CD Setup Runbook

This runbook configures GitHub Actions to build frontend and backend images in the dedicated Azure Container Registry and deploy two isolated Docker Compose stacks to the existing VM.

## Deployment Model

| Git branch | GitHub environment | Compose project | Mongo database | Initial port |
| --- | --- | --- | --- | --- |
| `develop` | `development` | `aladdin-dev` | `aladdin_dev` | `8080` |
| `main` | `production` | `aladdin-prod` | `aladdin_prod` | `80` |

Images use immutable commit tags:

```text
n4sacr.azurecr.io/aladdin/frontend:<git-sha>
n4sacr.azurecr.io/aladdin/backend:<git-sha>
```

The intended authentication path is GitHub OIDC. No long-lived Azure password is stored in GitHub.

> **Shared-host boundary:** development and production are separated by Compose projects, ports, databases, and volumes, but they are not a security boundary. Azure VM Run Command executes as root on the shared VM, so a compromised deployment workflow for either branch could affect both stacks. This is accepted for the hackathon. Require reviewed merges to `develop`, protect `main`, require CODEOWNER approval for `.github/workflows/` and `deploy/`, and move production to a separate host for stronger isolation.

## Step 1: Confirm Prerequisites

Run from PowerShell:

```powershell
az account set --subscription "BD-XDV-Learning-Sandbox"
az account show --query "{subscription:name, tenant:tenantId, id:id}" --output table
az resource show --resource-group "Need4Sleep" --resource-type "Microsoft.ContainerRegistry/registries" --name "n4sacr" --output table
az vm show --resource-group "Need4Sleep" --name "n4sServer" --output table
```

The operator must also be allowed to create managed identities, federated credentials, and role assignments. Owner is sufficient. Otherwise, combine Contributor or Managed Identity Contributor with Role Based Access Control Administrator, User Access Administrator, or equivalent custom permissions at the required scopes. `Contributor` alone cannot create role assignments, while an RBAC administrator alone cannot create the identity.

Expected identifiers:

```text
Subscription ID: 867cdad6-e31e-43db-94a0-ea0457112ddc
Tenant ID:       0ae51e19-07c8-4e4b-bb6d-648ee58410f4
Resource group:  Need4Sleep
Registry:        n4sacr.azurecr.io
VM:              n4sServer
Region:          southeastasia
```

## Step 2: Create the Development Branch

Create the integration branch after the one-time bootstrap pull request is merged into `main`:

```bash
git switch main
git pull --ff-only origin main
git switch -c develop
git push --set-upstream origin develop
```

In GitHub, set branch protection for both `develop` and `main`:

- Require a pull request before merging.
- Require at least one approval.
- Require conversation resolution.
- Require CI status checks after the first CI workflow has run.
- Block force pushes and branch deletion.
- Allow squash merging.
- Require CODEOWNER review for `.github/workflows/` and `deploy/` after a `CODEOWNERS` file is added.

Normal work targets `develop`. Only `develop` targets `main` for a release.

## Step 3: Create the GitHub Deployment Identity

First try a dedicated user-assigned managed identity. Enterprise Azure policy may require an administrator to perform or approve this step.

```powershell
$ResourceGroup = "Need4Sleep"
$Location = "southeastasia"
$IdentityName = "n4s-github-deploy"

az identity create `
  --resource-group $ResourceGroup `
  --name $IdentityName `
  --location $Location

$ClientId = az identity show `
  --resource-group $ResourceGroup `
  --name $IdentityName `
  --query clientId `
  --output tsv

$PrincipalId = az identity show `
  --resource-group $ResourceGroup `
  --name $IdentityName `
  --query principalId `
  --output tsv
```

Create one federated credential per GitHub Environment. Deployment triggers still select the environment from the branch, but GitHub's OIDC subject uses the environment name when a job declares an environment:

```powershell
az identity federated-credential create `
  --resource-group $ResourceGroup `
  --identity-name $IdentityName `
  --name "github-development" `
  --issuer "https://token.actions.githubusercontent.com" `
  --subject "repo:dom7hc/Aladdin:environment:development" `
  --audiences "api://AzureADTokenExchange"

az identity federated-credential create `
  --resource-group $ResourceGroup `
  --identity-name $IdentityName `
  --name "github-production" `
  --issuer "https://token.actions.githubusercontent.com" `
  --subject "repo:dom7hc/Aladdin:environment:production" `
  --audiences "api://AzureADTokenExchange"
```

If identity creation or federated credentials are denied, record the exact policy error and request a dedicated Entra application with the same two GitHub subjects. Do not reuse a personal login.

## Step 4: Assign Least-Scope Azure Roles

Give GitHub permission to push images and execute deployment commands on this VM only:

```powershell
$AcrId = az acr show `
  --resource-group $ResourceGroup `
  --name "n4sacr" `
  --query id `
  --output tsv

$VmId = az vm show `
  --resource-group $ResourceGroup `
  --name "n4sServer" `
  --query id `
  --output tsv

az role assignment create `
  --assignee-object-id $PrincipalId `
  --assignee-principal-type ServicePrincipal `
  --role "AcrPush" `
  --scope $AcrId

az role assignment create `
  --assignee-object-id $PrincipalId `
  --assignee-principal-type ServicePrincipal `
  --role "Virtual Machine Contributor" `
  --scope $VmId
```

`Virtual Machine Contributor` is acceptable for the hackathon but broader than the final requirement. Replace it later with a custom role limited to VM read and run-command operations.

Give the VM permission to pull images using its system-assigned identity:

```powershell
$VmPrincipalId = az vm show `
  --resource-group $ResourceGroup `
  --name "n4sServer" `
  --query identity.principalId `
  --output tsv

az role assignment create `
  --assignee-object-id $VmPrincipalId `
  --assignee-principal-type ServicePrincipal `
  --role "AcrPull" `
  --scope $AcrId
```

Allow several minutes for new role assignments to propagate.

## Step 5: Configure GitHub Variables and Environments

Open `Settings > Secrets and variables > Actions > Variables` in GitHub and add:

```text
AZURE_CLIENT_ID        = value of $ClientId
AZURE_TENANT_ID        = 0ae51e19-07c8-4e4b-bb6d-648ee58410f4
AZURE_SUBSCRIPTION_ID  = 867cdad6-e31e-43db-94a0-ea0457112ddc
AZURE_RESOURCE_GROUP   = Need4Sleep
AZURE_VM_NAME          = n4sServer
AZURE_REGISTRY         = n4sacr
```

Create GitHub environments named `development` and `production`. In each environment's deployment branch rules, allow only its matching branch:

```text
development -> develop only
production  -> main only
```

These restrictions are required because an environment-based OIDC subject does not contain the branch name. Production approval can remain disabled for automatic main deployments, or be enabled later without changing the workflow.

OIDC requires this workflow permission:

```yaml
permissions:
  contents: read
  id-token: write
```

Do not create `AZURE_CLIENT_SECRET` when OIDC succeeds.

## Step 6: Bootstrap the VM

The VM needs Docker Engine, the Compose plugin, Git, Azure CLI, and deployment directories. Run this bootstrap once through Azure VM Run Command or an approved SSH session:

```bash
#!/usr/bin/env bash
set -euo pipefail

sudo apt-get update
sudo apt-get install -y ca-certificates curl git gnupg

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

sudo install -d -m 0750 /opt/aladdin/development
sudo install -d -m 0750 /opt/aladdin/production
sudo install -d -m 0750 /opt/aladdin/releases

printf '%s\n' \
  '{' \
  '  "log-driver": "json-file",' \
  '  "log-opts": {' \
  '    "max-size": "10m",' \
  '    "max-file": "3"' \
  '  }' \
  '}' | sudo tee /etc/docker/daemon.json >/dev/null

sudo systemctl enable docker
sudo systemctl restart docker
sudo docker version
sudo docker compose version
az version
```

If Bosch proxy or certificate policy blocks package installation, stop and configure the approved proxy/CA trust. Do not disable TLS verification.

The bootstrap creates these directories:

```text
/opt/aladdin/development
/opt/aladdin/production
/opt/aladdin/releases
```

Required host behavior:

- Docker starts automatically after reboot.
- Docker logs rotate instead of filling the 30 GB OS disk.
- The VM signs in with managed identity before `az acr login`.
- Development and production use separate Compose project names and volumes.
- Runtime `runtime.env` files are root-owned, mode `0600`, and never committed.
- MongoDB credentials and the external LLM credential exist only in runtime configuration or Key Vault.

Create the protected runtime files before the first deployment:

```bash
sudo install -o root -g root -m 0600 /dev/null /opt/aladdin/development/runtime.env
sudo install -o root -g root -m 0600 /dev/null /opt/aladdin/production/runtime.env
sudoedit /opt/aladdin/development/runtime.env
sudoedit /opt/aladdin/production/runtime.env
```

Populate each file with the environment variables required by the backend, including its MongoDB connection and external LLM endpoint credentials. Use different database credentials where available. Do not echo secret values into terminal history or workflow logs.

Verify ACR access from the VM:

```bash
sudo az login --identity
sudo az acr login --name n4sacr
sudo docker pull n4sacr.azurecr.io/<test-image>:<tag>
```

The image pull test can only run after the first test image has been pushed.

## Step 7: Agree on the Application Contract

Do not enable required CI checks until these files and commands exist:

```text
frontend/Dockerfile
frontend/package.json
backend/Dockerfile
backend/pyproject.toml or backend/requirements.txt
deploy/compose.yml
```

Required validation commands:

```text
frontend: npm run lint, npm test, npm run build
backend:  configured lint command, pytest
runtime:  GET /health returns HTTP 200
```

The Compose file must accept these values without editing tracked files:

```text
IMAGE_TAG
DEPLOY_ENV
COMPOSE_PROJECT_NAME
MONGO_DATABASE
PUBLIC_PORT
```

It must route `GET /health` through the public frontend port so deployment verification can use `http://127.0.0.1:$PUBLIC_PORT/health` on the VM.

## Step 8: Add the CI Workflow

Create `.github/workflows/ci.yml` after the application contract lands.

The workflow should:

- Run for pull requests targeting `develop` or `main`.
- Run frontend and backend validation in parallel.
- Build both Docker images without pushing them.
- Use dependency and Docker layer caches.
- Cancel superseded runs for the same pull request.
- Expose stable check names for branch protection.

After the workflow has completed once, add its check names to the `develop` and `main` branch protection rules.

## Step 9: Add the Deployment Workflow

Create `.github/workflows/deploy.yml` with these controls:

- Trigger only on pushes to `develop` and `main`.
- Select `development` for `develop` and `production` for `main`.
- Use `azure/login` with OIDC and repository variables.
- Run `az acr login --name "$AZURE_REGISTRY"` on the GitHub runner before pushing images.
- Build and push frontend and backend images tagged with the full Git SHA.
- Never deploy a mutable `latest` tag.
- Use one VM-wide concurrency group such as `aladdin-vm-deployment` with `cancel-in-progress: false`; Azure VM Run Command permits only one active script and both environments share the host.
- Invoke the tracked `deploy/deploy.sh` through `az vm run-command invoke --scripts @deploy/deploy.sh`; do not open SSH to GitHub runners.
- Pull new images before replacing existing containers.
- Wait for `/health` and report container logs on failure.
- Restore the previous image tag if health verification fails.

Pass the Git SHA, deployment environment, Compose project, Mongo database, and public port to the script. The script must use the public repository to check out the exact deployed revision, so `deploy/compose.yml` always matches the images. The tracked `deploy/deploy.sh` should implement this complete flow:

```bash
#!/bin/sh
set -eu

IMAGE_TAG="$1"
DEPLOY_ENV="$2"
COMPOSE_PROJECT_NAME="$3"
MONGO_DATABASE="$4"
PUBLIC_PORT="$5"

ENV_DIR="/opt/aladdin/$DEPLOY_ENV"
RELEASE_DIR="/opt/aladdin/releases/$IMAGE_TAG"
REPOSITORY_DIR="/opt/aladdin/repository"

# Serialize development and production deployments on the shared VM.
exec 9>/var/lock/aladdin-deploy.lock
flock 9

if [ ! -d "$REPOSITORY_DIR/.git" ]; then
  git clone --filter=blob:none https://github.com/dom7hc/Aladdin.git "$REPOSITORY_DIR"
fi

git -C "$REPOSITORY_DIR" fetch --prune origin \
  "+refs/heads/*:refs/remotes/origin/*"
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

compose_for() {
  release_env="$1"
  shift
  release_tag="$(sed -n 's/^IMAGE_TAG=//p' "$release_env")"
  release_path="/opt/aladdin/releases/$release_tag"

  docker compose \
    --project-name "$COMPOSE_PROJECT_NAME" \
    --env-file "$ENV_DIR/runtime.env" \
    --env-file "$release_env" \
    --file "$release_path/deploy/compose.yml" \
    "$@"
}

check_health() {
  curl --fail --retry 12 --retry-delay 5 --retry-all-errors \
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

az login --identity
az acr login --name n4sacr

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
  exit 0
fi

rollback
```

`runtime.env` contains stable secrets and is created manually on the VM. `release.env.new` contains only non-secret release coordinates.

`current.env` always identifies the active successful release, while `previous.env` records the release before it. A failed first deployment is removed because no rollback target exists. Later failures restore `current.env` with `--remove-orphans`, verify rollback health, and still return a failed deployment status so GitHub reports the problem.

The workflow invocation should pass environment-specific values equivalent to:

```text
develop -> development, aladdin-dev,  aladdin_dev,  8080
main    -> production,  aladdin-prod, aladdin_prod, 80
```

The GitHub workflow should invoke the script with:

```bash
az vm run-command invoke \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --name "$AZURE_VM_NAME" \
  --command-id RunShellScript \
  --scripts @deploy/deploy.sh \
  --parameters \
    "imageTag=$GITHUB_SHA" \
    "deployEnv=$DEPLOY_ENV" \
    "composeProject=$COMPOSE_PROJECT_NAME" \
    "mongoDatabase=$MONGO_DATABASE" \
    "publicPort=$PUBLIC_PORT"
```

## Step 10: Configure Ingress

Initially expose production on TCP 80 and development on TCP 8080. Do not expose backend, worker, MongoDB, or Docker daemon ports.

Add HTTPS when a DNS name is available. Restrict TCP 22 to approved Bosch source ranges; the current rule allows SSH from every source.

## Step 11: Validate End to End

Test in this order:

1. Open a test pull request into `develop` and confirm CI runs without Azure write access.
2. Merge into `develop` and confirm both commit-tagged images appear in ACR.
3. Confirm only `aladdin-dev` changes on the VM.
4. Confirm the development health endpoint returns HTTP 200.
5. Open a release pull request from `develop` to `main`.
6. Merge and confirm only `aladdin-prod` changes.
7. Force a health-check failure with a test image and verify automatic rollback.
8. Re-run a successful deployment and confirm it is idempotent.

## Step 12: Add Retention and Operational Checks

After deployment works:

- Keep active and previous image tags.
- Delete older unreferenced ACR manifests on a schedule.
- Run `docker image prune` conservatively on the VM.
- Alert on failed GitHub deployments.
- Monitor VM disk usage, container restarts, and health status.
- Document manual rollback using a known successful Git SHA.
