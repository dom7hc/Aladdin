# Writes /opt/aladdin/<env>/runtime.env on the VM from Terraform outputs,
# then runs deploy/bootstrap-vm.sh (repository clone, Caddy, ACR check).
# Run from infra/ after `terraform apply` and after the admin has run the
# role assignment commands. Re-running overwrites runtime.env with current
# values, which is how a rotated key or password reaches the VM.
#
# Secrets travel inside the Run Command script body (base64, never printed
# here), are stored root-only on the VM, and never touch local disk.
param(
    [string]$ResourceGroup = 'Need4Sleep',
    [string]$VmName        = 'n4sServer',
    [string]$LlmModel      = 'deepseek',
    # Needs the backend's LLM_THINKING=omit support (fix/foundry-llm); older
    # code always sends `thinking`, which Foundry rejects.
    [bool]$LlmEnabled      = $true
)
$ErrorActionPreference = 'Stop'
$TerraformDir = Join-Path $PSScriptRoot 'terraform'
$RepoRoot     = Split-Path $PSScriptRoot -Parent

function Get-TfOutput([string]$Name) {
    $value = terraform -chdir="$TerraformDir" output -raw $Name
    if ($LASTEXITCODE -ne 0) { throw "terraform output $Name failed" }
    return $value
}

function Invoke-RunCommand([string]$ScriptPath, [string[]]$Parameters = @()) {
    $arguments = @('vm', 'run-command', 'invoke', '--resource-group', $ResourceGroup,
        '--name', $VmName, '--command-id', 'RunShellScript', '--scripts', "@$ScriptPath",
        '--output', 'json')
    if ($Parameters.Count -gt 0) { $arguments += @('--parameters') + $Parameters }
    $result = az @arguments | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { throw 'az vm run-command invoke failed' }
    $result.value | ForEach-Object { $_.message }
    # Run Command reports success even when the script fails; check the guest.
    if ($result.value | Where-Object { $_.code -notlike '*/succeeded' }) {
        throw "Script $ScriptPath failed on the VM"
    }
}

$hostname = Get-TfOutput 'public_hostname'
$registry = (terraform -chdir="$TerraformDir" output -json github_variables | ConvertFrom-Json).AZURE_REGISTRY

$common = @(
    "AZURE_REGISTRY=$registry"
    "MONGODB_URI=$(Get-TfOutput 'mongodb_uri')"
    "PUBLIC_BASE_URL=https://$hostname"
    "LLM_ENABLED=$($LlmEnabled.ToString().ToLower())"
    "LLM_BASE_URL=$(Get-TfOutput 'foundry_openai_base_url')"
    "LLM_API_KEY=$(Get-TfOutput 'foundry_api_key')"
    "LLM_MODEL=$LlmModel"
    # Foundry rejects the DeepSeek-only thinking field.
    "LLM_THINKING=omit"
) -join "`n"
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($common + "`n"))

# LF line endings: the script runs under bash on the VM.
$writeEnv = @'
#!/bin/bash
set -eu
# Docker's group only exists once cloud-init has finished installing it.
cloud-init status --wait >/dev/null || true
gid="$(getent group docker | cut -d: -f3)"
for env_name in development production; do
  dir="/opt/aladdin/$env_name"
  install -d -m 0750 "$dir"
  umask 077
  { echo "$1" | base64 -d; echo "DOCKER_GID=$gid"; } >"$dir/runtime.env.new"
  chown root:root "$dir/runtime.env.new"
  chmod 0600 "$dir/runtime.env.new"
  mv "$dir/runtime.env.new" "$dir/runtime.env"
  echo "Wrote $dir/runtime.env"
done
# bootstrap-vm.sh starts Caddy only from a cloned repository; deploy.sh
# clones the same way, so doing it here lets TLS come up before the first
# deployment.
if [ ! -d /opt/aladdin/repository/.git ]; then
  git clone --filter=blob:none https://github.com/dom7hc/Aladdin.git /opt/aladdin/repository
fi
'@ -replace "`r`n", "`n"

$scriptFile = Join-Path ([IO.Path]::GetTempPath()) 'aladdin-write-env.sh'
try {
    [IO.File]::WriteAllText($scriptFile, $writeEnv)
    Write-Host 'Writing runtime.env for both environments'
    Invoke-RunCommand $scriptFile @($encoded)
} finally {
    Remove-Item $scriptFile -ErrorAction SilentlyContinue
}

Write-Host 'Running deploy/bootstrap-vm.sh'
Invoke-RunCommand (Join-Path $RepoRoot 'deploy/bootstrap-vm.sh') @($registry)

Write-Host "VM configured. Next: set the GitHub variables and run the Deploy workflow."
