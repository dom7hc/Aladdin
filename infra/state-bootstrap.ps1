# Creates the Azure Storage container that holds Terraform state. Run once,
# before the first `terraform init`; re-running is safe.
#
# Kept outside Terraform on purpose: the state for the thing that stores
# state would have nowhere to live. The names must match backend.tf.
$ErrorActionPreference = 'Stop'

$Subscription   = '867cdad6-e31e-43db-94a0-ea0457112ddc'
$ResourceGroup  = 'aladdin-tfstate'
$StorageAccount = 'n4saladdintfstate'
$Container      = 'tfstate'
$Location       = 'southeastasia'

function Invoke-Az {
    az @args
    if ($LASTEXITCODE -ne 0) { throw "az $($args -join ' ') failed" }
}

Invoke-Az account set --subscription $Subscription

Invoke-Az group create --name $ResourceGroup --location $Location `
    --tags project=aladdin owner=dom7hc managed-by=state-bootstrap --output none

# Versioning and soft delete make an overwritten or deleted state recoverable.
Invoke-Az storage account create --name $StorageAccount --resource-group $ResourceGroup `
    --location $Location --sku Standard_LRS --kind StorageV2 `
    --min-tls-version TLS1_2 --allow-blob-public-access false --output none

Invoke-Az storage account blob-service-properties update `
    --account-name $StorageAccount --resource-group $ResourceGroup `
    --enable-versioning true --enable-delete-retention true --delete-retention-days 30 --output none

Invoke-Az storage container create --name $Container --account-name $StorageAccount `
    --auth-mode key --output none

Write-Host "State storage ready: $StorageAccount/$Container in $ResourceGroup"
