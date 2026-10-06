# Databricks notebook source
# MAGIC %md
# MAGIC # 05 — Publish (gold/metrics → gold/snapshots + $web)
# MAGIC Builds snapshot.json, validates it against the schema, and publishes it to the static site.

# COMMAND ----------

dbutils.widgets.text("run_date", "")
dbutils.widgets.text("config_dir", "")

# COMMAND ----------

from kiosque_pipeline import publish
from kiosque_pipeline.job import job_context

ctx = job_context(dbutils)
print(ctx.run_date, publish.run(ctx))
