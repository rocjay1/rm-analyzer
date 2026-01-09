resource "azurerm_service_plan" "plan" {
  name                = "${var.project_name}-plan"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  os_type             = "Linux"
  sku_name            = "Y1" # Consumption
}

resource "azurerm_linux_function_app" "app" {
  name                = "${var.project_name}-func-${local.resource_suffix}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location

  storage_account_name          = azurerm_storage_account.sa.name
  storage_uses_managed_identity = true
  service_plan_id               = azurerm_service_plan.plan.id
  
  https_only                 = true

  identity {
    type = "SystemAssigned"
  }

  site_config {
    application_stack {
      python_version = "3.11"
    }
    ftps_state = "Disabled"
  }

  app_settings = {
    "AzureWebJobsStorage__accountName"       = azurerm_storage_account.sa.name
    "AzureWebJobsStorage__credential"        = "managedidentity"
    "FUNCTIONS_WORKER_RUNTIME"               = "python"
    "FUNCTIONS_EXTENSION_VERSION"            = "~4"
    "RM_ANALYZER_STORAGE_ACCOUNT_URL"        = azurerm_storage_account.sa.primary_blob_endpoint
    # robustly extract endpoint from connection string to avoid region hardcoding
    "COMMUNICATION_SERVICES_ENDPOINT"        = replace(regex("endpoint=[^;]+", azurerm_communication_service.comm_svc.primary_connection_string), "endpoint=", "")
    "SENDER_EMAIL"                           = "DoNotReply@${azurerm_email_communication_service_domain.domain.from_sender_domain}"
    "BUILD_FLAGS"                            = "UseElf"
    "SCM_DO_BUILD_DURING_DEPLOYMENT"         = "true"
    "ENABLE_ORYX_BUILD"                      = "true"
  }
}
