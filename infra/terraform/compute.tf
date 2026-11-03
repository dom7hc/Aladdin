# The VM's SSH key. The private half is stored in state (which is why state
# must be private) and exposed as a sensitive output for break-glass access.
# Day to day nothing uses SSH: deployments go through Run Command.
resource "tls_private_key" "vm" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "azurerm_linux_virtual_machine" "main" {
  name                  = local.names.vm
  location              = azurerm_resource_group.main.location
  resource_group_name   = azurerm_resource_group.main.name
  size                  = var.vm_size
  network_interface_ids = [azurerm_network_interface.vm.id]
  tags                  = local.tags

  admin_username                  = "azureuser"
  disable_password_authentication = true

  admin_ssh_key {
    username   = "azureuser"
    public_key = tls_private_key.vm.public_key_openssh
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "StandardSSD_LRS"
    disk_size_gb         = var.vm_os_disk_gb
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }

  # The VM signs in to Azure as itself (az login --identity) to pull images.
  # AcrPull on the registry is granted to this identity's principal ID.
  identity {
    type = "SystemAssigned"
  }

  # Lets you use the serial console from the portal if the VM stops booting.
  boot_diagnostics {}

  # First-boot setup: Docker, Azure CLI, folders, log rotation.
  custom_data = base64encode(file("${path.module}/cloud-init.yaml"))

  lifecycle {
    # Changing custom_data would make Terraform destroy and recreate the VM,
    # and cloud-init only runs on first boot anyway. Edits to cloud-init.yaml
    # therefore apply only to a freshly built VM, never to this one.
    #
    # A subscription policy attaches its own user-assigned identity
    # (Built-In-Identity-southeastasia) to every VM. Removing it would only
    # see the policy add it back, so the identity block is left as Azure has
    # it; the system identity's principal_id is still read on every refresh.
    ignore_changes = [custom_data, identity]
  }
}
