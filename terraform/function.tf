resource "azurerm_service_plan" "plan" {
  name                = "${var.project_name}-plan"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  os_type             = "Linux"
  sku_name            = "Y1" # Dynamic / Consumption
}

resource "azurerm_linux_function_app" "app" {
  name                = "${var.project_name}-func-${local.resource_suffix}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location

  service_plan_id = azurerm_service_plan.plan.id

  storage_account_name       = azurerm_storage_account.sa.name
  storage_account_access_key = azurerm_storage_account.sa.primary_access_key

  site_config {
    application_stack {
      use_custom_runtime = true
    }
  }

  lifecycle {
    ignore_changes = [
      tags,
      app_settings["APPINSIGHTS_INSTRUMENTATIONKEY"],
      app_settings["APPLICATIONINSIGHTS_CONNECTION_STRING"]
    ]
  }

  app_settings = {
    "APPLICATIONINSIGHTS_CONNECTION_STRING" = azurerm_application_insights.app_insights.connection_string
    "APPINSIGHTS_INSTRUMENTATIONKEY"        = azurerm_application_insights.app_insights.instrumentation_key
    "FUNCTIONS_WORKER_RUNTIME"              = "custom"
    "BLOB_SERVICE_URL"                      = azurerm_storage_account.sa.primary_blob_endpoint
    "QUEUE_SERVICE_URL"                     = azurerm_storage_account.sa.primary_queue_endpoint
    "TABLE_SERVICE_URL"                     = azurerm_storage_account.sa.primary_table_endpoint
    # Robustly extract endpoint from connection string to avoid region hardcoding
    # Note: Regex usage might need adjustment if connection string format varies, but usually stable.
    "COMMUNICATION_SERVICES_ENDPOINT" = replace(regex("endpoint=[^;]+", azurerm_communication_service.comm_svc.primary_connection_string), "endpoint=", "")
    "SENDER_EMAIL"                    = "DoNotReply@${azurerm_email_communication_service_domain.domain.from_sender_domain}"
    "BLOB_CONTAINER_NAME"             = "csv-uploads"
    "QUEUE_NAME"                      = "csv-processing"
    "TRANSACTIONS_TABLE"              = "transactions"
    "SAVINGS_TABLE"                   = "savings"
    "PEOPLE_TABLE"                    = "people"
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
