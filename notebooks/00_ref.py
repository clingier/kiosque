# Databricks notebook source
# MAGIC %md
# MAGIC # 00 — Reference data (config → ref.sources, ref.groups)
# MAGIC Loads sources.yaml / groups.yaml into Unity Catalog so ownership is traceable.

# COMMAND ----------

dbutils.widgets.text("run_date", "")
dbutils.widgets.text("config_dir", "")
dbutils.widgets.text("catalog", "kiosque")

# COMMAND ----------

from kiosque_pipeline.job import job_context
from kiosque_pipeline.steps import ref

ctx = job_context(dbutils, spark)
print(ctx.run_date, ref.run(ctx))
