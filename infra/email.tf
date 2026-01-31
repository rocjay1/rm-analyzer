resource "azurerm_email_communication_service" "email_svc" {
  name                = "${var.project_name}-email-${local.resource_suffix}"
  resource_group_name = azurerm_resource_group.rg.name
  data_location       = var.data_location
}

resource "azurerm_communication_service" "comm_svc" {
  name                = "${var.project_name}-comm-${local.resource_suffix}"
  resource_group_name = azurerm_resource_group.rg.name
  data_location       = var.data_location
}

# Note: Managed Domains often require manual verification or DNS configuration that might take time.
# For simplicity in this plan, we provision the domain resource but users might need to check portal status.
resource "azurerm_email_communication_service_domain" "domain" {
  name              = "roccosmodernsite.net"
  email_service_id  = azurerm_email_communication_service.email_svc.id
  domain_management = "CustomerManaged"
}

resource "azurerm_communication_service_email_domain_association" "assoc" {
  communication_service_id = azurerm_communication_service.comm_svc.id
  email_service_domain_id  = azurerm_email_communication_service_domain.domain.id
}

resource "azurerm_role_assignment" "comm_svc_contributor" {
  scope                = azurerm_communication_service.comm_svc.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_function_app_flex_consumption.app.identity[0].principal_id
}
