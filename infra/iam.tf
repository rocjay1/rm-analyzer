# Grant the user running Terraform access to the storage account data plane
# This is required because shared keys are disabled, so Terraform needs RBAC to poll/verify the resource
resource "azurerm_role_assignment" "tf_user_blob_owner" {
  scope                = azurerm_storage_account.sa.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = data.azurerm_client_config.current.object_id
}

# Communication Services Access
resource "azurerm_role_assignment" "comm_svc_contributor" {
  scope                = azurerm_communication_service.comm_svc.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_function_app_flex_consumption.app.identity[0].principal_id
}

# Storage Roles (Required for Keyless AzureWebJobsStorage)
# Blob Data Owner is required for the Functions Host to manage leases and artifacts
resource "azurerm_role_assignment" "storage_blob_owner" {
  scope                = azurerm_storage_account.sa.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = azurerm_function_app_flex_consumption.app.identity[0].principal_id
}

# Queue Data Contributor is required for internal coordination triggers
resource "azurerm_role_assignment" "storage_queue_contributor" {
  scope                = azurerm_storage_account.sa.id
  role_definition_name = "Storage Queue Data Contributor"
  principal_id         = azurerm_function_app_flex_consumption.app.identity[0].principal_id
}

# Table Data Contributor is required for internal coordination (checkpoints/timers)
resource "azurerm_role_assignment" "storage_table_contributor" {
  scope                = azurerm_storage_account.sa.id
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = azurerm_function_app_flex_consumption.app.identity[0].principal_id
}
