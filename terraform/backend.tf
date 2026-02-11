terraform {
  backend "azurerm" {
    resource_group_name  = "rg-tfstate"
    storage_account_name = "q9pp4eqfiwkpmklctfstate"
    container_name       = "tfstate"
    key                  = "rm-analyzer.tfstate"
    use_azuread_auth     = true
  }
}
