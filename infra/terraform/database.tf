# Letters and digits only, so the password goes into MONGODB_URI without
# percent-encoding. 32 characters from three classes still meets the
# cluster's complexity rule.
resource "random_password" "mongo" {
  length      = 32
  special     = false
  min_upper   = 2
  min_lower   = 2
  min_numeric = 2
}

resource "azurerm_mongo_cluster" "main" {
  name                   = local.names.mongo
  location               = azurerm_resource_group.main.location
  resource_group_name    = azurerm_resource_group.main.name
  administrator_username = "aladdinadmin"
  administrator_password = random_password.mongo.result
  compute_tier           = var.mongo_compute_tier
  storage_size_in_gb     = var.mongo_storage_gb
  high_availability_mode = "Disabled"
  shard_count            = 1
  version                = "7.0"

  # Reachable only through the private endpoint below, from inside the vnet.
  public_network_access = "Disabled"
  tags                  = local.tags

  lifecycle {
    # Project data lives here. A plan that would replace or destroy the
    # cluster fails instead; remove this deliberately if that is ever wanted.
    prevent_destroy = true
  }
}

# Resolves <cluster>.mongocluster.cosmos.azure.com to the private endpoint's
# address for anything in the vnet, so the public hostname in MONGODB_URI
# keeps working without public access.
resource "azurerm_private_dns_zone" "mongo" {
  name                = "privatelink.mongocluster.cosmos.azure.com"
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "mongo" {
  name                  = "mongo-to-vnet"
  resource_group_name   = azurerm_resource_group.main.name
  private_dns_zone_name = azurerm_private_dns_zone.mongo.name
  virtual_network_id    = azurerm_virtual_network.main.id
  tags                  = local.tags
}

resource "azurerm_private_endpoint" "mongo" {
  name                = "${local.names.mongo}-pe"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = azurerm_subnet.private_endpoints.id
  tags                = local.tags

  private_service_connection {
    name                           = "${local.names.mongo}-connection"
    private_connection_resource_id = azurerm_mongo_cluster.main.id
    subresource_names              = ["MongoCluster"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "mongo"
    private_dns_zone_ids = [azurerm_private_dns_zone.mongo.id]
  }
}
