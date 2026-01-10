data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "rg" {
  name     = "${var.project_name}-rg"
  location = var.location
}

resource "azurerm_consumption_budget_resource_group" "budget" {
  name              = "${var.project_name}-budget"
  resource_group_id = azurerm_resource_group.rg.id
  amount            = 5
  time_grain        = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01'T'00:00:00Z", timestamp())
  }

  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThanOrEqualTo"
    threshold_type = "Actual"

    contact_roles = [
      "Owner",
      "Contributor",
    ]
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThanOrEqualTo"
    threshold_type = "Actual"

    contact_roles = [
      "Owner",
    ]
  }

  lifecycle {
    ignore_changes = [
      time_period,
    ]
  }
}

resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

locals {
  resource_suffix = random_string.suffix.result
}
