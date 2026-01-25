resource "azurerm_service_plan" "plan" {
  name                = "${var.project_name}-plan"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  os_type             = "Linux"
  sku_name            = "FC1" # Flex Consumption
}

resource "azurerm_function_app_flex_consumption" "app" {
  name                = "${var.project_name}-func-${local.resource_suffix}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location

  service_plan_id = azurerm_service_plan.plan.id

  storage_container_endpoint  = "${azurerm_storage_account.sa.primary_blob_endpoint}${azurerm_storage_container.deployment.name}"
  storage_container_type      = "blobContainer"
  storage_authentication_type = "SystemAssignedIdentity"

  runtime_name    = "python"
  runtime_version = "3.12"

  identity {
    type = "SystemAssigned"
  }

  site_config {}

  lifecycle {
    ignore_changes = [
      tags,
      auth_settings_v2,
      site_config,
      app_settings["APPINSIGHTS_INSTRUMENTATIONKEY"],
      app_settings["APPLICATIONINSIGHTS_CONNECTION_STRING"]
    ]
  }

  app_settings = {
    "APPLICATIONINSIGHTS_CONNECTION_STRING" = azurerm_application_insights.app_insights.connection_string
    "APPINSIGHTS_INSTRUMENTATIONKEY"        = azurerm_application_insights.app_insights.instrumentation_key
    # Workaround for known issue: explicit empty connection string
    "AzureWebJobsStorage"                    = ""
    "AzureWebJobsStorage__accountName"       = azurerm_storage_account.sa.name
    "AzureWebJobsStorage__credential"        = "managedidentity"
    "DEPLOYMENT_STORAGE_AUTHENTICATION_TYPE" = "SystemAssignedIdentity"
    "DEPLOYMENT_STORAGE_ACCOUNT_NAME"        = azurerm_storage_account.sa.name
    "BLOB_SERVICE_URL"                       = azurerm_storage_account.sa.primary_blob_endpoint
    "QUEUE_SERVICE_URL"                      = azurerm_storage_account.sa.primary_queue_endpoint
    "TABLE_SERVICE_URL"                      = azurerm_storage_account.sa.primary_table_endpoint
    "StorageConnection__blobServiceUri"      = azurerm_storage_account.sa.primary_blob_endpoint
    "StorageConnection__queueServiceUri"     = azurerm_storage_account.sa.primary_queue_endpoint
    # Robustly extract endpoint from connection string to avoid region hardcoding
    "COMMUNICATION_SERVICES_ENDPOINT" = replace(regex("endpoint=[^;]+", azurerm_communication_service.comm_svc.primary_connection_string), "endpoint=", "")
    "SENDER_EMAIL"                    = "DoNotReply@${azurerm_email_communication_service_domain.domain.from_sender_domain}"
    "BUILD_FLAGS"                     = "UseElf"
  }
}

resource "azurerm_log_analytics_workspace" "logs" {
  name                = "${var.project_name}-logs-${local.resource_suffix}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_application_insights" "app_insights" {
  name                = "${var.project_name}-insights-${local.resource_suffix}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  workspace_id        = azurerm_log_analytics_workspace.logs.id
  application_type    = "web"
}
