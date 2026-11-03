locals {
  # Reusing the pre-deletion names keeps docs, workflows and the Caddyfile valid.
  names = {
    resource_group  = "Need4Sleep"
    vnet            = "vnet-southeastasia-1"
    subnet_vm       = "snet-vm"
    subnet_private  = "snet-private-endpoints"
    nsg             = "n4sServer-nsg"
    public_ip       = "n4sServer-ip"
    nic             = "n4sServer-nic"
    vm              = "n4sServer"
    acr             = "n4sacr"            # globally unique, letters and digits only
    mongo           = "n4s-docdb-cluster" # globally unique
    deploy_identity = "n4s-github-deploy"
    foundry         = "n4s-aladdin-foundry" # also its globally unique subdomain
  }

  # Public hostname: n4s-aladdin.southeastasia.cloudapp.azure.com.
  # deploy/caddy/Caddyfile depends on this exact value.
  dns_label = "n4s-aladdin"

  # Inbound ports open to the internet. Caddy owns all of them; every app
  # container binds to loopback only.
  public_ports = {
    "http"      = "80"        # HTTP -> HTTPS redirect and ACME challenges
    "https"     = "443"       # production
    "dev-https" = "8443"      # development
    "previews"  = "9001-9010" # PoC preview slots
  }

  tags = {
    project    = "aladdin"
    owner      = "dom7hc"
    managed-by = "terraform"
  }
}
