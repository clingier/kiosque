# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Metrics (silver.story_articles → gold.story_metrics, gold.day_kpis)
# MAGIC HHI, dominant group and blind spots per story; day KPIs.

# COMMAND ----------

dbutils.widgets.text("run_date", "")
dbutils.widgets.text("config_dir", "")
dbutils.widgets.text("catalog", "kiosque")

# COMMAND ----------

from kiosque_pipeline.steps import metrics
from kiosque_pipeline.job import job_context

ctx = job_context(dbutils, spark)
print(ctx.run_date, metrics.run(ctx))
