######################################################################
# variables.tf – Input variables
######################################################################

variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
  sensitive   = true
}

variable "project_name" {
  description = "Project name used in the naming convention for all resources"
  type        = string
  default     = "kiosque"
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "northeurope"
}

variable "environment" {
  description = "Deployment environment (prod, staging, dev)"
  type        = string
  default     = "prod"
}

variable "enable_functions" {
  description = "Whether to provision the collector Function App (Flex Consumption)"
  type        = bool
  default     = false
}

variable "enable_cdn" {
  description = "Whether to provision CDN profile and endpoint"
  type        = bool
  default     = false
}

variable "databricks_sku" {
  description = "Databricks workspace SKU (premium required for Workflows)"
  type        = string
  default     = "premium"
}

variable "alert_email" {
  description = "Email address that receives monitoring alerts"
  type        = string
}

variable "pipeline_principals" {
  description = "Users (email) or service principal application IDs (GUID) that run the Databricks job. AUTHORITATIVE: anyone not listed loses their grants on catalog kiosque. In CI, set secret PIPELINE_PRINCIPALS to a JSON list, e.g. [\"you@example.com\"]."
  type        = list(string)

  validation {
    condition = length(var.pipeline_principals) > 0 && alltrue([
      for p in var.pipeline_principals :
      can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", p)) || can(regex("^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$", p))
    ])
    error_message = "pipeline_principals must list at least one user email or service principal application ID (GUID). The catalog grants are authoritative, so a missing or malformed entry would revoke access."
  }
}
