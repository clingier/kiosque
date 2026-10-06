# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Normalize (raw.feeds → bronze.articles, bronze.collections)
# MAGIC Merges `raw/feeds/<run_date>/*.json` into `bronze/articles/<run_date>.json`.

# COMMAND ----------

dbutils.widgets.text("run_date", "")
dbutils.widgets.text("config_dir", "")
dbutils.widgets.text("catalog", "kiosque")

# COMMAND ----------

from kiosque_pipeline.steps import normalize
from kiosque_pipeline.job import job_context

ctx = job_context(dbutils, spark)
print(ctx.run_date, normalize.run(ctx))
