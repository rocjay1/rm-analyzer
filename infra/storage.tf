resource "azurerm_storage_account" "sa" {
  name                     = "${replace(var.project_name, "-", "")}sa${local.resource_suffix}"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  min_tls_version            = "TLS1_2"
  https_traffic_only_enabled = true

  # ENFORCE KEYLESS: Disable Account Keys and Public Access
  shared_access_key_enabled       = false
  allow_nested_items_to_be_public = false
}

resource "azurerm_storage_container" "deployment" {
  name                  = "deployment-packages"
  storage_account_id    = azurerm_storage_account.sa.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "csv" {
  name                  = "csv-uploads"
  storage_account_id    = azurerm_storage_account.sa.id
  container_access_type = "private"
}

resource "azurerm_storage_queue" "csv" {
  name               = "csv-processing"
  storage_account_id = azurerm_storage_account.sa.id
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

# Queue Data Message Processor is required for Function App to process queue messages
resource "azurerm_role_assignment" "storage_queue_message_processor" {
  scope                = azurerm_storage_account.sa.id
  role_definition_name = "Storage Queue Data Message Processor"
  principal_id         = azurerm_function_app_flex_consumption.app.identity[0].principal_id
}

# Table Data Contributor is required for internal coordination
resource "azurerm_role_assignment" "storage_table_contributor" {
  scope                = azurerm_storage_account.sa.id
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = azurerm_function_app_flex_consumption.app.identity[0].principal_id
}

# Grant the user running Terraform access to the storage account data plane
# This is required because shared keys are disabled, so Terraform needs RBAC to poll/verify the resource
resource "azurerm_role_assignment" "tf_user_blob_owner" {
  scope                = azurerm_storage_account.sa.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "tf_user_queue_contributor" {
  scope                = azurerm_storage_account.sa.id
  role_definition_name = "Storage Queue Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "tf_user_table_contributor" {
  scope                = azurerm_storage_account.sa.id
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}
