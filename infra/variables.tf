variable "project_name" {
  type        = string
  default     = "rmanalyzer"
  description = "Base name for the project resources"
}

variable "location" {
  type        = string
  default     = "eastus"
  description = "Azure region for resources"
}

variable "swa_location" {
  type        = string
  default     = "eastus2"
  description = "Region for Static Web App (must be a supported region)"
}

variable "data_location" {
  type        = string
  default     = "United States"
  description = "Data location for Communication Services"
}

variable "subscription_id" {
  type        = string
  description = "Target Azure Subscription ID"
}

variable "cloudflare_api_token" {
  description = "API token with permissions for DNS edits and Zero Trust tunnel management."
  type        = string
  sensitive   = true
}

variable "account_id" {
  description = "Cloudflare account ID."
  type        = string
}

variable "zone_id" {
  description = "Cloudflare zone ID."
  type        = string
}

variable "zone_name" {
  description = "Cloud zone name"
  type        = string
}