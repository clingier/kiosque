######################################################################
# storage.tf – ADLS Gen2 account, medallion containers, static website
######################################################################

# Storage account names cannot contain hyphens → stkiosqueprod
resource "azurerm_storage_account" "main" {
  name                     = "st${var.project_name}${var.environment}"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  # Hierarchical namespace makes this ADLS Gen2 (immutable after creation)
  is_hns_enabled = true

  tags = azurerm_resource_group.main.tags
}

# Static website config (separate resource per azurerm v4.x / v5.x)
resource "azurerm_storage_account_static_website" "main" {
  storage_account_id = azurerm_storage_account.main.id
  index_document     = "kiosque.html"
}

# ---------------------------------------------------------------------
# Medallion-layer containers
# NOTE: The $web container is auto-created by the static_website block
#       and must NOT be declared here.
# ---------------------------------------------------------------------
locals {
  medallion_containers = ["raw", "bronze", "silver", "gold"]
}

resource "azurerm_storage_container" "medallion" {
  for_each = toset(local.medallion_containers)

  name                  = each.value
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}
