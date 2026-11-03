resource "azurerm_virtual_network" "main" {
  name                = local.names.vnet
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  address_space       = ["10.20.0.0/16"]
  tags                = local.tags
}

# The VM's subnet.
resource "azurerm_subnet" "vm" {
  name                 = local.names.subnet_vm
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.20.1.0/24"]
}

# Holds the database's private endpoint, so the database gets an address inside
# the vnet and needs no public access.
resource "azurerm_subnet" "private_endpoints" {
  name                 = local.names.subnet_private
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.20.2.0/24"]
}

resource "azurerm_network_security_group" "vm" {
  name                = local.names.nsg
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

# One rule per entry in local.public_ports. Priorities follow the sorted keys,
# so they stay stable however the map is written.
resource "azurerm_network_security_rule" "public" {
  for_each = local.public_ports

  name                        = "allow-${each.key}"
  priority                    = 100 + index(sort(keys(local.public_ports)), each.key) * 10
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = each.value
  source_address_prefix       = "Internet"
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.vm.name
}

# SSH only from listed ranges; with none listed the rule does not exist and
# port 22 stays closed. Deployments use Run Command, which needs no open port.
resource "azurerm_network_security_rule" "ssh" {
  count = length(var.ssh_allowed_cidrs) > 0 ? 1 : 0

  name                        = "allow-ssh"
  priority                    = 300
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "22"
  source_address_prefixes     = var.ssh_allowed_cidrs
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.vm.name
}

# Static, so the address survives VM stop/start. The DNS label gives the
# hostname n4s-aladdin.southeastasia.cloudapp.azure.com.
resource "azurerm_public_ip" "vm" {
  name                = local.names.public_ip
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
  domain_name_label   = local.dns_label
  tags                = local.tags
}

resource "azurerm_network_interface" "vm" {
  name                = local.names.nic
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags

  ip_configuration {
    name                          = "primary"
    subnet_id                     = azurerm_subnet.vm.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.vm.id
  }
}

resource "azurerm_network_interface_security_group_association" "vm" {
  network_interface_id      = azurerm_network_interface.vm.id
  network_security_group_id = azurerm_network_security_group.vm.id
}
