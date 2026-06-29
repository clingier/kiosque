######################################################################
# main.tf – Provider configuration, backend & resource group
######################################################################

terraform {
  required_version = ">= 1.5"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }

  backend "azurerm" {
    resource_group_name  = "rg-kiosque-tfstate"
    storage_account_name = "stkiosquetfstate"
    container_name       = "tfstate"
    key                  = "kiosque.prod.terraform.tfstate"
  }
}

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
    key_vault {
      purge_soft_delete_on_destroy = true
    }
  }

  subscription_id = var.subscription_id
}

# ---------------------------------------------------------------------
# Resource Group
# ---------------------------------------------------------------------
resource "azurerm_resource_group" "main" {
  name     = "rg-${var.project_name}-${var.environment}"
  location = var.location

  tags = {
    project    = var.project_name
    env        = var.environment
    managed_by = "terraform"
  }
}
