# Communication Services Access
resource "azurerm_role_assignment" "comm_svc_contributor" {
  scope                = azurerm_communication_service.comm_svc.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_linux_function_app.app.identity[0].principal_id
}

# Storage Roles (Required for Keyless AzureWebJobsStorage)
# Blob Data Owner is required for the Functions Host to manage leases and artifacts
resource "azurerm_role_assignment" "storage_blob_owner" {
  scope                = azurerm_storage_account.sa.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = azurerm_linux_function_app.app.identity[0].principal_id
}

# Queue Data Contributor is required for internal coordination triggers
resource "azurerm_role_assignment" "storage_queue_contributor" {
  scope                = azurerm_storage_account.sa.id
  role_definition_name = "Storage Queue Data Contributor"
  principal_id         = azurerm_linux_function_app.app.identity[0].principal_id
}

# Table Data Contributor is required for internal coordination (checkpoints/timers)
resource "azurerm_role_assignment" "storage_table_contributor" {
  scope                = azurerm_storage_account.sa.id
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = azurerm_linux_function_app.app.identity[0].principal_id
}
