resource "azurerm_static_site" "web" {
  name                = "${var.project_name}-web-${local.resource_suffix}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = var.swa_location
  sku_tier            = "Standard"
  sku_size            = "Standard"

  app_settings = {
    "AZURE_CLIENT_ID"     = azuread_application_registration.frontend_app.client_id
    "AZURE_CLIENT_SECRET" = azuread_application_password.frontend_secret.value
  }
}

output "static_web_app_url" {
  value = azurerm_static_site.web.default_host_name
}

output "function_app_name" {
  value = azurerm_linux_function_app.app.name
}

output "resource_group_name" {
  value = azurerm_resource_group.rg.name
}
