resource "azurerm_static_web_app" "web" {
  name                = "${var.project_name}-web-${local.resource_suffix}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = var.swa_location
  sku_tier            = "Standard"
  sku_size            = "Standard"

  lifecycle {
    ignore_changes = [
      repository_url,
      repository_branch
    ]
  }
}

resource "azurerm_static_web_app_function_app_registration" "backend" {
  static_web_app_id = azurerm_static_web_app.web.id
  function_app_id   = azurerm_function_app_flex_consumption.app.id
}
