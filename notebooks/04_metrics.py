# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Metrics (silver/enriched → gold/metrics)
# MAGIC HHI, dominant group and blind spots per story; day KPIs.

# COMMAND ----------

dbutils.widgets.text("run_date", "")
dbutils.widgets.text("config_dir", "")

# COMMAND ----------

from kiosque_pipeline import metrics
from kiosque_pipeline.job import job_context

ctx = job_context(dbutils)
print(ctx.run_date, metrics.run(ctx))
