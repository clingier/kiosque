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
  description = "Whether to provision Function App (requires App Service VM quota)"
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
