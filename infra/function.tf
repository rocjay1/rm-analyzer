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

  site_config {
  }

  auth_settings_v2 {
    auth_enabled = false
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
    "RM_ANALYZER_STORAGE_ACCOUNT_URL"        = azurerm_storage_account.sa.primary_blob_endpoint
    # robustly extract endpoint from connection string to avoid region hardcoding
    "COMMUNICATION_SERVICES_ENDPOINT" = replace(regex("endpoint=[^;]+", azurerm_communication_service.comm_svc.primary_connection_string), "endpoint=", "")
    "SENDER_EMAIL"                    = "DoNotReply@${azurerm_email_communication_service_domain.domain.from_sender_domain}"
    "BUILD_FLAGS"                     = "UseElf"
    "SCM_DO_BUILD_DURING_DEPLOYMENT"  = "true"
    "ENABLE_ORYX_BUILD"               = "true"
  }
}
