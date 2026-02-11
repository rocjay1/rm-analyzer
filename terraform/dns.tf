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
  content    = "\"${azurerm_email_communication_service_domain.domain.verification_records[0].domain[0].value}\""
  proxied    = false
  ttl        = 1
  depends_on = [azurerm_email_communication_service_domain.domain]
}

resource "cloudflare_dns_record" "azure_spf" {
  zone_id    = var.zone_id
  name       = azurerm_email_communication_service_domain.domain.verification_records[0].spf[0].name
  type       = "TXT"
  content    = "\"${azurerm_email_communication_service_domain.domain.verification_records[0].spf[0].value}\""
  proxied    = false
  ttl        = 1
  depends_on = [azurerm_email_communication_service_domain.domain]
}

resource "cloudflare_dns_record" "azure_dkim" {
  zone_id    = var.zone_id
  name       = azurerm_email_communication_service_domain.domain.verification_records[0].dkim[0].name
  type       = "CNAME"
  content    = azurerm_email_communication_service_domain.domain.verification_records[0].dkim[0].value
  proxied    = false
  ttl        = 1
  depends_on = [azurerm_email_communication_service_domain.domain]
}

resource "cloudflare_dns_record" "azure_dkim2" {
  zone_id    = var.zone_id
  name       = azurerm_email_communication_service_domain.domain.verification_records[0].dkim2[0].name
  type       = "CNAME"
  content    = azurerm_email_communication_service_domain.domain.verification_records[0].dkim2[0].value
  proxied    = false
  ttl        = 1
  depends_on = [azurerm_email_communication_service_domain.domain]
}

resource "cloudflare_dns_record" "azure_swa" {
  zone_id    = var.zone_id
  name       = "rm-analyzer"
  type       = "CNAME"
  content    = azurerm_static_web_app.web.default_host_name
  proxied    = true
  ttl        = 1
  depends_on = [azurerm_static_web_app.web]
}

resource "cloudflare_ruleset" "geoblock" {
  zone_id     = var.zone_id
  name        = "Geo Block"
  description = "Block non-US traffic"
  kind        = "zone"
  phase       = "http_request_firewall_custom"

  rules = [{
    action      = "block"
    expression  = "(ip.src.country ne \"US\")"
    description = "Block non-US traffic"
    enabled     = true
  }]
}
