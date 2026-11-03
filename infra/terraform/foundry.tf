# Azure Foundry resource with the model deployments the agents call. It sits
# in var.foundry_location because Claude is not offered in southeastasia.
# Both models are reached through the OpenAI-compatible endpoint
# https://<subdomain>.openai.azure.com/openai/v1/ with the account key.
resource "azurerm_cognitive_account" "foundry" {
  count = var.enable_foundry ? 1 : 0

  name                  = local.names.foundry
  location              = var.foundry_location
  resource_group_name   = azurerm_resource_group.main.name
  kind                  = "AIServices"
  sku_name              = "S0"
  custom_subdomain_name = local.names.foundry
  local_auth_enabled    = true
  tags                  = local.tags
}

# Keyed by deployment name, which is what the backend sends as the model.
# Drop an entry from var.foundry_deployments and re-apply to remove just that
# one.
resource "azurerm_cognitive_deployment" "models" {
  for_each = var.enable_foundry ? var.foundry_deployments : {}

  name                 = each.key
  cognitive_account_id = azurerm_cognitive_account.foundry[0].id

  model {
    format  = each.value.format
    name    = each.value.model
    version = each.value.version
  }

  sku {
    name     = "GlobalStandard"
    capacity = each.value.capacity
  }
}

# Claude, deployed as "claude". Anthropic models are a Marketplace offer and
# the API refuses them without modelProviderData, which azurerm cannot send,
# so this one goes through azapi as a raw ARM request.
resource "azapi_resource" "claude" {
  count = var.enable_foundry && var.claude_deployment != null ? 1 : 0

  type      = "Microsoft.CognitiveServices/accounts/deployments@2025-12-01"
  name      = "claude"
  parent_id = azurerm_cognitive_account.foundry[0].id

  # The bundled schema predates modelProviderData; the API itself accepts it.
  schema_validation_enabled = false

  body = {
    sku = {
      name     = "GlobalStandard"
      capacity = var.claude_deployment.capacity
    }
    properties = {
      model = {
        format  = "Anthropic"
        name    = var.claude_deployment.model
        version = var.claude_deployment.version
      }
      modelProviderData = {
        industry         = var.claude_deployment.industry
        organizationName = var.claude_deployment.organization_name
        countryCode      = var.claude_deployment.country_code
      }
    }
  }

  # Two deployments on one account at once fail with RequestConflict.
  depends_on = [azurerm_cognitive_deployment.models]
}
