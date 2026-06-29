######################################################################
# databricks.tf – Databricks workspace (shell only)
######################################################################

# Terraform provisions the workspace shell. Notebooks, clusters,
# workflows, and mounts are configured outside of Terraform
# (via Databricks CLI, Databricks TF provider, or manually).

resource "azurerm_databricks_workspace" "main" {
  name                        = "dbw-${var.project_name}-${var.environment}"
  resource_group_name         = azurerm_resource_group.main.name
  location                    = azurerm_resource_group.main.location
  sku                         = var.databricks_sku
  managed_resource_group_name = "rg-${var.project_name}-databricks-managed"

  tags = azurerm_resource_group.main.tags
}
