data "cloudflare_account" "main" {
  account_id = var.account_id
}

data "cloudflare_zone" "main" {
  zone_id = var.zone_id
}

resource "cloudflare_zone_dnssec" "main_zone_dnssec" {
  zone_id             = data.cloudflare_zone.main.zone_id
  dnssec_multi_signer = false
  dnssec_presigned    = false
  dnssec_use_nsec3    = false
  status              = "active"

  lifecycle {
    ignore_changes = all
  }
}

resource "cloudflare_dns_record" "azure_verification_txt" {
  zone_id    = var.zone_id
  name       = azurerm_email_communication_service_domain.domain.verification_records[0].domain[0].name
  type       = "TXT"
  content    = azurerm_email_communication_service_domain.domain.verification_records[0].domain[0].value
  proxied    = false
  ttl        = 60
  depends_on = [azurerm_email_communication_service_domain.domain]
}

resource "cloudflare_dns_record" "azure_spf" {
  zone_id    = var.zone_id
  name       = azurerm_email_communication_service_domain.domain.verification_records[0].spf[0].name
  type       = "TXT"
  content    = azurerm_email_communication_service_domain.domain.verification_records[0].spf[0].value
  proxied    = false
  ttl        = 60
  depends_on = [azurerm_email_communication_service_domain.domain]
}

resource "cloudflare_dns_record" "azure_dkim" {
  zone_id    = var.zone_id
  name       = azurerm_email_communication_service_domain.domain.verification_records[0].dkim[0].name
  type       = "CNAME"
  content    = azurerm_email_communication_service_domain.domain.verification_records[0].dkim[0].value
  proxied    = false
  ttl        = 60
  depends_on = [azurerm_email_communication_service_domain.domain]
}

resource "cloudflare_dns_record" "azure_dkim2" {
  zone_id    = var.zone_id
  name       = azurerm_email_communication_service_domain.domain.verification_records[0].dkim2[0].name
  type       = "CNAME"
  content    = azurerm_email_communication_service_domain.domain.verification_records[0].dkim2[0].value
  proxied    = false
  ttl        = 60
  depends_on = [azurerm_email_communication_service_domain.domain]
}
