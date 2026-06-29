######################################################################
# cdn.tf – CDN profile + endpoint (behind var.enable_cdn toggle)
######################################################################

# CDN is optional at M0. Set var.enable_cdn = true when DNS is ready.
# Custom domain and TLS are configured manually after DNS propagation.

resource "azurerm_cdn_profile" "main" {
  count = var.enable_cdn ? 1 : 0

  name                = "cdn-${var.project_name}-${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Standard_Microsoft"

  tags = azurerm_resource_group.main.tags
}

resource "azurerm_cdn_endpoint" "static_website" {
  count = var.enable_cdn ? 1 : 0

  name                = "cdne-${var.project_name}-${var.environment}"
  profile_name        = azurerm_cdn_profile.main[0].name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  origin_host_header = azurerm_storage_account.main.primary_web_host

  origin {
    name      = "static-website"
    host_name = azurerm_storage_account.main.primary_web_host
  }

  tags = azurerm_resource_group.main.tags
}
