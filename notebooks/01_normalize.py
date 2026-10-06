# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Normalize (raw → bronze)
# MAGIC Merges `raw/feeds/<run_date>/*.json` into `bronze/articles/<run_date>.json`.

# COMMAND ----------

dbutils.widgets.text("run_date", "")
dbutils.widgets.text("config_dir", "")

# COMMAND ----------

from kiosque_pipeline import normalize
from kiosque_pipeline.job import job_context

ctx = job_context(dbutils)
print(ctx.run_date, normalize.run(ctx))
