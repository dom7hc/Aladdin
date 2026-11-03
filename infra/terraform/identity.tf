# The identity GitHub Actions signs in as. No secret exists: GitHub presents
# a short-lived OIDC token and Azure trusts it through the federated
# credentials below.
resource "azurerm_user_assigned_identity" "deploy" {
  name                = local.names.deploy_identity
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

# One credential per GitHub environment. The subject uses the immutable
# owner/repo IDs, which is what this repository's tokens carry.
resource "azurerm_federated_identity_credential" "github" {
  for_each = var.github_environments

  name                      = "github-${each.key}"
  user_assigned_identity_id = azurerm_user_assigned_identity.deploy.id
  issuer                    = "https://token.actions.githubusercontent.com"
  audience                  = ["api://AzureADTokenExchange"]
  subject                   = "${var.github_oidc_subject_prefix}:environment:${each.key}"
}

# Role assignments need Owner or Role Based Access Control Administrator.
# With manage_role_assignments = false (Contributor only), none of these are
# created and the admin_role_assignment_commands output prints them instead.
locals {
  role_assignments = {
    deploy-acrpush = {
      scope     = azurerm_container_registry.main.id
      role      = "AcrPush"
      principal = azurerm_user_assigned_identity.deploy.principal_id
    }
    deploy-vm-contributor = {
      scope     = azurerm_linux_virtual_machine.main.id
      role      = "Virtual Machine Contributor"
      principal = azurerm_user_assigned_identity.deploy.principal_id
    }
    vm-acrpull = {
      scope     = azurerm_container_registry.main.id
      role      = "AcrPull"
      principal = azurerm_linux_virtual_machine.main.identity[0].principal_id
    }
  }
}

resource "azurerm_role_assignment" "main" {
  for_each = var.manage_role_assignments ? local.role_assignments : {}

  scope                = each.value.scope
  role_definition_name = each.value.role
  principal_id         = each.value.principal
  principal_type       = "ServicePrincipal"
}
