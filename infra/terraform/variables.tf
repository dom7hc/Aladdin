variable "location" {
  description = "Region for the VM, network, registry and db."
  type        = string
  default     = "southeastasia"
}

variable "vm_size" {
  description = "Host both app stacks plus up to 10 poc previews"
  type        = string
  default     = "Standard_B4ms"
}

variable "vm_os_disk_gb" {
  description = "OS disk size"
  type        = number
  default     = 64
}

variable "ssh_allowed_cidrs" {
  description = ""
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for c in var.ssh_allowed_cidrs : can(cidrhost(c, 0))])
    error_message = "entry must be cidr"
  }
}

variable "mongo_compute_tier" {
  description = "Cosmos DB"
  type        = string
  default     = "M10"
}
variable "mongo_storage_gb" {
  description = "Cosmos DB for MongoDB (vCore) storage size."
  type        = number
  default     = 32
}
variable "github_oidc_subject_prefix" {
  description = ""
  type        = string
  default     = "repo:dom7hc@260634561/Aladdin@1394518314"
}

variable "github_environments" {
  description = "github env"
  type        = set(string)
  default     = ["development", "production"]
}

variable "manage_role_assignments" {
  description = "Create role assignments in Terraform. Needs Owner or RBAC Administrator; when false, outputs.tf prints the commands for an admin."
  type        = bool
  default     = false
}

variable "enable_foundry" {
  description = "Build the Azure Foundry resource and model deployments."
  type        = bool
  default     = true
}

variable "foundry_location" {
  description = "Foundry region. Claude is not offered in southeastasia; eastus2 has both Claude and DeepSeek."
  type        = string
  default     = "eastus2"
}

variable "foundry_deployments" {
  description = "Model deployments on the Foundry resource, keyed by deployment name."
  type = map(object({
    format   = string
    model    = string
    version  = string
    capacity = number
  }))
  default = {
    "deepseek" = {
      format   = "DeepSeek"
      model    = "DeepSeek-V4.1-Flash"
      version  = "2026-09-10"
      capacity = 50
    }
  }
}

variable "claude_deployment" {
  description = <<-EOT
    The Claude deployment, kept apart from foundry_deployments because
    Anthropic models require modelProviderData (the organization deploying
    them), which azurerm cannot send. null leaves Claude out.
  EOT
  type = object({
    model             = string
    version           = string
    capacity          = number
    industry          = string
    organization_name = string
    country_code      = string
  })
  default = null
}
