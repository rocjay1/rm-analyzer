data "azurerm_client_config" "current" {}

resource "azuread_application_registration" "frontend_app" {
  display_name     = "${var.project_name}-frontend"
  sign_in_audience = "AzureADMyOrg" # Restrict to this tenant only

  implicit_access_token_issuance_enabled = false
  implicit_id_token_issuance_enabled     = true
}

resource "azuread_service_principal" "frontend_sp" {
  client_id                    = azuread_application_registration.frontend_app.client_id
  app_role_assignment_required = true # Require user assignment for access
}

resource "azuread_application_password" "frontend_secret" {
  application_id = azuread_application_registration.frontend_app.id
}

resource "azuread_application_redirect_uris" "swa_callback" {
  application_id = azuread_application_registration.frontend_app.id
  type           = "Web"

  redirect_uris = [
    "https://${azurerm_static_web_app.web.default_host_name}/.auth/login/aad/callback"
  ]
}
