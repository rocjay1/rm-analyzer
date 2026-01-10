resource "azurerm_storage_account" "sa" {
  name                     = "${replace(var.project_name, "-", "")}sa${local.resource_suffix}"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  min_tls_version          = "TLS1_2"
  https_traffic_only_enabled = true

  # ENFORCE KEYLESS: Disable Account Keys and Public Access
  shared_access_key_enabled      = false
  allow_nested_items_to_be_public = false
}

resource "azurerm_storage_container" "deployment" {
  name                  = "deployment-packages"
  storage_account_id    = azurerm_storage_account.sa.id
  container_access_type = "private"
}