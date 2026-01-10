resource "azuread_application_registration" "github_actions" {
  display_name = "${var.project_name}-github-actions"
}

resource "azuread_service_principal" "github_actions" {
  client_id = azuread_application_registration.github_actions.client_id
}

resource "azuread_application_federated_identity_credential" "github_oidc" {
  application_id = azuread_application_registration.github_actions.id
  display_name   = "github-actions-oidc"
  description    = "Deploy from GitHub Actions"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_repo}:environment:production"
}

resource "azurerm_role_assignment" "github_deployer" {
  scope                = azurerm_resource_group.rg.id
  role_definition_name = "Contributor"
  principal_id         = azuread_service_principal.github_actions.object_id
}
