######################################################################
# unity_catalog.tf – Unity Catalog for the Kiosque pipeline
# Catalog `kiosque` (managed tables on stkiosqueprod/unity) + external
# volume on the collector's raw container. All objects are free.
######################################################################

resource "azurerm_databricks_access_connector" "kiosque" {
  name                = "dbac-${var.project_name}-${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  identity {
    type = "SystemAssigned"
  }

  tags = azurerm_resource_group.main.tags
}

resource "azurerm_role_assignment" "unity_storage" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_databricks_access_connector.kiosque.identity[0].principal_id
}

resource "azurerm_storage_container" "unity" {
  name                  = "unity"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

resource "databricks_storage_credential" "kiosque" {
  name = "kiosque"

  azure_managed_identity {
    access_connector_id = azurerm_databricks_access_connector.kiosque.id
  }

  depends_on = [azurerm_role_assignment.unity_storage]
}

resource "databricks_external_location" "raw" {
  name            = "kiosque_raw"
  url             = "abfss://raw@${azurerm_storage_account.main.name}.dfs.core.windows.net/"
  credential_name = databricks_storage_credential.kiosque.name
  read_only       = true
}

resource "databricks_external_location" "unity" {
  name            = "kiosque_unity"
  url             = "abfss://${azurerm_storage_container.unity.name}@${azurerm_storage_account.main.name}.dfs.core.windows.net/"
  credential_name = databricks_storage_credential.kiosque.name
}

resource "databricks_catalog" "kiosque" {
  name                           = "kiosque"
  comment                        = "Kiosque medallion tables (managed) — lineage from raw feeds to published snapshots"
  storage_root                   = databricks_external_location.unity.url
  enable_predictive_optimization = "DISABLE"
}

resource "databricks_schema" "layers" {
  for_each = toset(["ref", "raw", "bronze", "silver", "gold"])

  catalog_name = databricks_catalog.kiosque.name
  name         = each.value
}

resource "databricks_volume" "feeds" {
  name             = "feeds"
  catalog_name     = databricks_catalog.kiosque.name
  schema_name      = databricks_schema.layers["raw"].name
  volume_type      = "EXTERNAL"
  storage_location = "${databricks_external_location.raw.url}feeds"
}

resource "databricks_grants" "kiosque" {
  catalog = databricks_catalog.kiosque.name

  dynamic "grant" {
    for_each = toset(var.pipeline_principals)
    content {
      principal  = grant.value
      privileges = ["USE_CATALOG", "USE_SCHEMA", "SELECT", "MODIFY", "CREATE_TABLE", "READ_VOLUME"]
    }
  }
}

output "unity_catalog_name" {
  description = "Unity Catalog catalog holding the pipeline tables"
  value       = databricks_catalog.kiosque.name
}
