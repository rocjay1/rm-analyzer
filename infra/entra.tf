data "azurerm_client_config" "current" {}

# 1. App Registration (Modern Resource)
resource "azuread_application_registration" "frontend_app" {
  display_name     = "${var.project_name}-frontend"
  sign_in_audience = "AzureADMyOrg" # Restrict to this tenant only

  implicit_access_token_issuance_enabled = false
  implicit_id_token_issuance_enabled     = false
}

# 2. Service Principal (Enterprise App)
resource "azuread_service_principal" "frontend_sp" {
  client_id                    = azuread_application_registration.frontend_app.client_id
  app_role_assignment_required = true # STRICT: User assignment required
}

# 3. Client Secret for the App
resource "azuread_application_password" "frontend_secret" {
  application_id = azuread_application_registration.frontend_app.id
}

# 4. Register the SWA Redirect URI (Callback)
# This resource IS compatible with azuread_application_registration
resource "azuread_application_redirect_uris" "swa_callback" {
  application_id = azuread_application_registration.frontend_app.id
  type           = "Web"

  redirect_uris = [
    "https://${azurerm_static_site.web.default_host_name}/.auth/login/aad/callback"
  ]
}

output "tenant_id" {
  value = data.azurerm_client_config.current.tenant_id
}
