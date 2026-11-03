# State lives in Azure Storage, outside the app's resource group, so a sweep
# of Need4Sleep does not take the state with it. Created once by
# infra/state-bootstrap.ps1. Backend blocks cannot use variables, hence the
# literal names.
#
# Storage key auth (the default): Terraform fetches the account key with
# your az login, which Contributor allows. Blob data roles are not needed.
terraform {
  backend "azurerm" {
    subscription_id      = "867cdad6-e31e-43db-94a0-ea0457112ddc"
    resource_group_name  = "aladdin-tfstate"
    storage_account_name = "n4saladdintfstate"
    container_name       = "tfstate"
    key                  = "aladdin.tfstate"
  }
}
