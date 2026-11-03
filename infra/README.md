# Aladdin infrastructure

Terraform for everything the deploy pipeline runs on. Terraform builds the
platform; GitHub Actions (`.github/workflows/deploy.yml`) deploys the app.

| File | What it builds |
|---|---|
| `terraform/main.tf` | Resource group `Need4Sleep` |
| `terraform/network.tf` | Vnet, VM and private-endpoint subnets, NSG (80, 443, 8443, 9001-9010; SSH only from `ssh_allowed_cidrs`), static public IP with DNS label `n4s-aladdin` |
| `terraform/compute.tf` + `cloud-init.yaml` | Ubuntu 24.04 VM `n4sServer` with a system identity; Docker, Compose and Azure CLI on first boot |
| `terraform/registry.tf` | Container registry `n4sacr` (no admin user) |
| `terraform/database.tf` | Cosmos DB for MongoDB vCore `n4s-docdb-cluster`, private endpoint only, `prevent_destroy` |
| `terraform/identity.tf` | GitHub deploy identity `n4s-github-deploy`, federated credentials, optional role assignments |
| `terraform/foundry.tf` | Azure Foundry `n4s-aladdin-foundry` in eastus2 with a `deepseek` deployment, and `claude` when `claude_deployment` is set |
| `terraform/backend.tf` | Remote state in `aladdin-tfstate/n4saladdintfstate` |

## Rebuild from nothing

Needs `az login` on the `BD-XDV-Learning-Sandbox` subscription with
Contributor, and Terraform 1.9+.

```powershell
# 1. State storage (once; safe to re-run)
./infra/state-bootstrap.ps1

# 2. Build
cd infra/terraform
terraform init
terraform plan -out tfplan      # read it: expect only creates on a rebuild
terraform apply tfplan

# 3. Role assignments: Contributor cannot create them. Send this to an admin.
terraform output -raw admin_role_assignment_commands

# 4. GitHub repository variables (only AZURE_CLIENT_ID changes on a rebuild)
terraform output -json github_variables

# 5. After the admin confirms: runtime.env, repository clone, Caddy, ACR check
cd ..
./configure-vm.ps1

# 6. Run the Deploy workflow for develop and main
```

With Owner rights, set `manage_role_assignments = true` in `terraform.tfvars`
and Terraform creates the three assignments itself; step 3 disappears.

## Things to know

- **Secrets live in state.** The Mongo password, Foundry key and VM SSH key
  are in the state blob in plain text. Access to `aladdin-tfstate` is access
  to all of them. Outputs holding them are marked sensitive; read one with
  `terraform output -raw <name>`.
- **`prevent_destroy` on the database.** A plan that would replace or delete
  the cluster fails. That is the point; remove it deliberately if needed.
- **`cloud-init.yaml` runs once.** Edits only reach a newly built VM.
  Terraform ignores changes to it so an edit never replaces the running VM.
- **Watch for `-/+` in plans.** It means destroy and recreate.
- **Claude on Foundry** is a Marketplace offer, and the API refuses it without
  `modelProviderData` (industry, organization name, country code), which
  azurerm cannot send. It is therefore an `azapi_resource` driven by
  `claude_deployment` in `terraform.tfvars`. `null` (the default) means it is
  not deployed. `enable_foundry = false` removes Foundry entirely.
- **LLM mode is off on the VM.** `app/agents/llm.py` always sends a `thinking`
  field, which Foundry rejects. Once the backend stops sending it, run
  `./configure-vm.ps1 -LlmEnabled $true`.
- **The corporate proxy can hang a run.** Terraform has no request timeout of
  its own. If a run stalls, stop it, check that no terraform process is left,
  then run `terraform force-unlock <id>`; the ID is in the error the next run
  prints. If an apply was cut short, something can exist in Azure without
  being in state: `terraform import` it rather than deleting it.
- **After an admin sweep**, if state survived, `terraform apply` recreates
  what is missing. If the state resource group went too, start at step 1.
- Git Bash mangles `/subscriptions/...` arguments to `az`; use PowerShell or
  set `MSYS_NO_PATHCONV=1`.
