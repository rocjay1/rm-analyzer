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
    cors {
      allowed_origins = ["https://${azurerm_static_site.web.default_host_name}"]
    }
    ftps_state = "FtpsOnly"
  }

  app_settings = {
    "AzureWebJobsStorage__accountName"       = azurerm_storage_account.sa.name
    "RM_ANALYZER_STORAGE_ACCOUNT_URL"        = azurerm_storage_account.sa.primary_blob_endpoint
    "COMMUNICATION_SERVICES_ENDPOINT"        = "https://${azurerm_communication_service.comm_svc.name}.unitedstates.communication.azure.com"
    "BUILD_FLAGS"                            = "UseElf"
    "SCM_DO_BUILD_DURING_DEPLOYMENT"         = "true"
    "ENABLE_ORYX_BUILD"                      = "true"
  }
}
