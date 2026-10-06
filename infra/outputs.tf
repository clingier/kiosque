######################################################################
# outputs.tf – Resource IDs, endpoints, connection strings
######################################################################

output "resource_group_name" {
  description = "Name of the resource group"
  value       = azurerm_resource_group.main.name
}

output "storage_account_name" {
  description = "Name of the ADLS Gen2 storage account"
  value       = azurerm_storage_account.main.name
}

output "static_website_url" {
  description = "Primary endpoint of the $web static site"
  value       = azurerm_storage_account.main.primary_web_endpoint
}

output "function_app_name" {
  description = "Name of the Function App"
  value       = var.enable_functions ? azurerm_linux_function_app.main[0].name : null
}

output "function_app_default_hostname" {
  description = "Default hostname (URL) of the Function App"
  value       = var.enable_functions ? azurerm_linux_function_app.main[0].default_hostname : null
}

output "databricks_workspace_url" {
  description = "URL of the Databricks workspace"
  value       = azurerm_databricks_workspace.main.workspace_url
}

output "appinsights_connection_string" {
  description = "Connection string for Application Insights"
  value       = azurerm_application_insights.main.connection_string
  sensitive   = true
}

output "datalake_connection_string" {
  description = "ADLS connection string — stored in the Databricks secret scope 'kiosque'"
  value       = azurerm_storage_account.main.primary_connection_string
  sensitive   = true
}
