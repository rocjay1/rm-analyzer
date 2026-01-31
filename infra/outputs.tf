output "static_web_app_url" {
  value       = "https://${azurerm_static_web_app.web.default_host_name}"
  description = "The URL of the Static Web App"
}

output "function_app_name" {
  value       = azurerm_function_app_flex_consumption.app.name
  description = "The name of the Function App"
}

output "tenant_id" {
  value       = data.azurerm_client_config.current.tenant_id
  description = "The Azure Tenant ID"
}

output "azure_client_id" {
  value       = azuread_application_registration.github_actions.client_id
  description = "The Client ID of the Service Principal for GitHub Actions"
}