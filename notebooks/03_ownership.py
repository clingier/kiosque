# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Ownership (silver/stories → silver/enriched)
# MAGIC Tags each article with its media's owner group (sources.yaml).

# COMMAND ----------

dbutils.widgets.text("run_date", "")
dbutils.widgets.text("config_dir", "")

# COMMAND ----------

from kiosque_pipeline import ownership
from kiosque_pipeline.job import job_context

ctx = job_context(dbutils)
print(ctx.run_date, ownership.run(ctx))
