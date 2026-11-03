data "azurerm_client_config" "current" {}

locals {
  public_hostname = azurerm_public_ip.vm.fqdn

  # The cluster reports its connection string with <user> and <password>
  # placeholders; the password has no characters that need encoding.
  mongodb_uri = replace(
    replace(
      azurerm_mongo_cluster.main.connection_strings[0].value,
      "<user>", azurerm_mongo_cluster.main.administrator_username
    ),
    "<password>", random_password.mongo.result
  )
}

# --- For the admin -------------------------------------------------------------

output "admin_role_assignment_commands" {
  description = "Send these to a subscription Owner when manage_role_assignments is false."
  value = var.manage_role_assignments ? "Role assignments are managed by Terraform." : join("\n", [
    for k, ra in local.role_assignments :
    "az role assignment create --assignee-object-id ${ra.principal} --assignee-principal-type ServicePrincipal --role \"${ra.role}\" --scope \"${ra.scope}\""
  ])
}

# --- For GitHub (repository variables read by deploy.yml) ----------------------

output "github_variables" {
  description = "Repository variables for .github/workflows/deploy.yml."
  value = {
    AZURE_CLIENT_ID       = azurerm_user_assigned_identity.deploy.client_id
    AZURE_TENANT_ID       = data.azurerm_client_config.current.tenant_id
    AZURE_SUBSCRIPTION_ID = data.azurerm_client_config.current.subscription_id
    AZURE_RESOURCE_GROUP  = azurerm_resource_group.main.name
    AZURE_VM_NAME         = azurerm_linux_virtual_machine.main.name
    AZURE_REGISTRY        = azurerm_container_registry.main.name
  }
}

# --- For the VM (written into runtime.env by infra/configure-vm.ps1) -----------

output "public_hostname" {
  value = local.public_hostname
}

output "public_ip" {
  value = azurerm_public_ip.vm.ip_address
}

output "foundry_openai_base_url" {
  description = "OpenAI-compatible base URL; the deployment name is the model."
  value       = var.enable_foundry ? "https://${local.names.foundry}.openai.azure.com/openai/v1/" : null
}

output "foundry_deployments" {
  value = concat(keys(azurerm_cognitive_deployment.models), azapi_resource.claude[*].name)
}

output "foundry_api_key" {
  value     = var.enable_foundry ? azurerm_cognitive_account.foundry[0].primary_access_key : null
  sensitive = true
}

output "mongodb_uri" {
  value     = local.mongodb_uri
  sensitive = true
}

output "vm_ssh_private_key" {
  description = "Break-glass only; port 22 is closed unless ssh_allowed_cidrs is set."
  value       = tls_private_key.vm.private_key_openssh
  sensitive   = true
}
