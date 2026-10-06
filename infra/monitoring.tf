######################################################################
# monitoring.tf – Application Insights + Log Analytics backing store
######################################################################

# App Insights v2 requires a Log Analytics workspace as its backing store.
resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-${var.project_name}-${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = azurerm_resource_group.main.tags
}

resource "azurerm_application_insights" "main" {
  name                = "appi-${var.project_name}-${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"

  tags = azurerm_resource_group.main.tags
}

# ---------------------------------------------------------------------
# Alerting — one email action group, three log-based alerts on App Insights.
# Databricks job failures are emailed by the job itself (databricks.yml).
# ---------------------------------------------------------------------
resource "azurerm_monitor_action_group" "email" {
  name                = "ag-${var.project_name}-${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = var.project_name

  email_receiver {
    name                    = "owner"
    email_address           = var.alert_email
    use_common_alert_schema = true
  }

  tags = azurerm_resource_group.main.tags
}

locals {
  log_alerts = {
    collector-failure-rate = {
      description          = "More than 5 sources failed during the daily collection"
      query                = "traces | where message startswith \"HIGH FAILURE RATE\""
      operator             = "GreaterThan"
      threshold            = 0
      evaluation_frequency = "PT1H"
      window_duration      = "PT1H"
    }
    collector-not-run = {
      description          = "The collect_feeds function has not run in the last 24 hours"
      query                = "requests | where operation_Name == \"collect_feeds\""
      operator             = "LessThan"
      threshold            = 1
      evaluation_frequency = "PT6H"
      window_duration      = "P1D"
    }
    snapshot-stale = {
      description          = "snapshot.json on the static site is not dated today"
      query                = "traces | where message startswith \"STALE SNAPSHOT\""
      operator             = "GreaterThan"
      threshold            = 0
      evaluation_frequency = "PT1H"
      window_duration      = "PT1H"
    }
  }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "log" {
  for_each = local.log_alerts

  name                 = "alert-${var.project_name}-${each.key}"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  description          = each.value.description
  scopes               = [azurerm_application_insights.main.id]
  severity             = 2
  evaluation_frequency = each.value.evaluation_frequency
  window_duration      = each.value.window_duration

  criteria {
    query                   = each.value.query
    time_aggregation_method = "Count"
    operator                = each.value.operator
    threshold               = each.value.threshold

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.email.id]
  }

  tags = azurerm_resource_group.main.tags
}
