output "function_app_name" {
  value = azurerm_function_app_flex_consumption.app.name
}

output "function_app_default_hostname" {
  value = azurerm_function_app_flex_consumption.app.default_hostname
}

output "static_web_app_name" {
  value = azurerm_static_web_app.web.name
}

output "static_web_app_default_hostname" {
  value = azurerm_static_web_app.web.default_host_name
}

output "email_verification_records" {
  value = {
    domain = azurerm_email_communication_service_domain.domain.verification_records[0].domain[0]
    spf    = azurerm_email_communication_service_domain.domain.verification_records[0].spf[0]
    dkim   = azurerm_email_communication_service_domain.domain.verification_records[0].dkim[0]
    dkim2  = azurerm_email_communication_service_domain.domain.verification_records[0].dkim2[0]
  }
}
