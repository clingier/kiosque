######################################################################
# functions.tf – Function App on Flex Consumption (FC1)
# Gated behind var.enable_functions
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
# Deployment package container (Flex Consumption pulls the app zip from it)
# ---------------------------------------------------------------------
resource "azurerm_storage_container" "deployments" {
  count = var.enable_functions ? 1 : 0

  name                  = "deployments"
  storage_account_id    = azurerm_storage_account.functions[0].id
  container_access_type = "private"
}

# ---------------------------------------------------------------------
# Flex Consumption plan (FC1) — serverless, scales to zero, and draws on
# its own regional quota rather than the App Service VM quota (0 on this
# subscription, which blocked the classic Y1 plan).
# ---------------------------------------------------------------------
resource "azurerm_service_plan" "functions" {
  count = var.enable_functions ? 1 : 0

  name                = "asp-${var.project_name}-${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = "FC1"

  tags = azurerm_resource_group.main.tags
}

# ---------------------------------------------------------------------
# Function App on Flex Consumption (Python 3.12)
# ---------------------------------------------------------------------
resource "azurerm_function_app_flex_consumption" "main" {
  count = var.enable_functions ? 1 : 0

  name                = "func-${var.project_name}-${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  service_plan_id     = azurerm_service_plan.functions[0].id

  storage_container_type      = "blobContainer"
  storage_container_endpoint  = "${azurerm_storage_account.functions[0].primary_blob_endpoint}${azurerm_storage_container.deployments[0].name}"
  storage_authentication_type = "StorageAccountConnectionString"
  storage_access_key          = azurerm_storage_account.functions[0].primary_access_key

  runtime_name           = "python"
  runtime_version        = "3.12"
  maximum_instance_count = 40
  instance_memory_in_mb  = 2048

  site_config {
    application_insights_connection_string = azurerm_application_insights.main.connection_string
  }

  # AzureWebJobsStorage comes from the storage_* arguments above; App Insights
  # from site_config. Setting them here too causes a permanent plan diff.
  app_settings = {
    # Data-lake storage connection (the main ADLS account)
    DATALAKE_STORAGE_CONNECTION_STRING = azurerm_storage_account.main.primary_connection_string
    DATALAKE_STORAGE_ACCOUNT_NAME      = azurerm_storage_account.main.name

    # Raw container written by the collector
    CONTAINER_RAW = "raw"
  }

  tags = azurerm_resource_group.main.tags
}
