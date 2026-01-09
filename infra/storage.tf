resource "azurerm_storage_account" "sa" {
  name                     = "${var.project_name}sa${local.resource_suffix}"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  min_tls_version          = "TLS1_2"
  https_traffic_only_enabled = true
}