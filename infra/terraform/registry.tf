# Holds the commit-tagged images that deploy.yml builds. Admin user stays off:
# GitHub pushes with its federated identity (AcrPush) and the VM pulls with
# its system identity (AcrPull), so no registry password exists anywhere.
resource "azurerm_container_registry" "main" {
  name                = local.names.acr
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "Basic"
  admin_enabled       = false
  tags                = local.tags
}
