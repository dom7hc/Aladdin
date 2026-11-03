terraform {
  required_version = ">= 1.9"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    #Generates the VM's SSH key.

    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
    #Generates the db admin password.
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    # Raw ARM requests, for the Claude deployment's modelProviderData,
    # which azurerm does not support.
    azapi = {
      source  = "azure/azapi"
      version = "~> 2.0"
    }
  }
}

provider "azurerm" {
  features {}

  # Pinned so a run can never land in whichever subscription `az account`
  # happens to point at.
  subscription_id = "867cdad6-e31e-43db-94a0-ea0457112ddc" # BD-XDV-Learning-Sandbox
}

provider "azapi" {
  subscription_id = "867cdad6-e31e-43db-94a0-ea0457112ddc"
}
