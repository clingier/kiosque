######################################################################
# functions.tf – Function App + App Service Plan (Consumption)
# Gated behind var.enable_functions (requires App Service VM quota)
######################################################################

# ---------------------------------------------------------------------
# Dedicated storage for the Function App runtime (AzureWebJobsStorage).
# ADLS Gen2 (HNS) can cause issues with Functions blob triggers,
# so we provision a separate standard account.
# ---------------------------------------------------------------------
resource "azurerm_storage_account" "functions" {
  count = var.enable_functions ? 1 : 0

  name                     = "st${var.project_name}func${var.environment}"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  tags = azurerm_resource_group.main.tags
}

# ---------------------------------------------------------------------
# Consumption App Service Plan (Linux)
# ---------------------------------------------------------------------
resource "azurerm_service_plan" "functions" {
  count = var.enable_functions ? 1 : 0

  name                = "asp-${var.project_name}-${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = "Y1"

  tags = azurerm_resource_group.main.tags
}

# ---------------------------------------------------------------------
# Linux Function App (Python 3.11)
# ---------------------------------------------------------------------
resource "azurerm_linux_function_app" "main" {
  count = var.enable_functions ? 1 : 0

  name                       = "func-${var.project_name}-${var.environment}"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  service_plan_id            = azurerm_service_plan.functions[0].id
  storage_account_name       = azurerm_storage_account.functions[0].name
  storage_account_access_key = azurerm_storage_account.functions[0].primary_access_key

  site_config {
    application_stack {
      python_version = "3.11"
    }
  }

  app_settings = {
    # Runtime
    FUNCTIONS_WORKER_RUNTIME = "python"

    # Monitoring
    APPLICATIONINSIGHTS_CONNECTION_STRING = azurerm_application_insights.main.connection_string

    # Data-lake storage connection (the main ADLS account)
    DATALAKE_STORAGE_CONNECTION_STRING = azurerm_storage_account.main.primary_connection_string
    DATALAKE_STORAGE_ACCOUNT_NAME      = azurerm_storage_account.main.name

    # Medallion container names
    CONTAINER_RAW    = "raw"
    CONTAINER_BRONZE = "bronze"
    CONTAINER_SILVER = "silver"
    CONTAINER_GOLD   = "gold"
  }

  tags = azurerm_resource_group.main.tags
}
