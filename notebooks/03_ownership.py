# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Ownership (silver.stories + ref.sources → silver.story_articles)
# MAGIC Tags each article with its media's owner group (sources.yaml).

# COMMAND ----------

dbutils.widgets.text("run_date", "")
dbutils.widgets.text("config_dir", "")
dbutils.widgets.text("catalog", "kiosque")

# COMMAND ----------

from kiosque_pipeline.steps import ownership
from kiosque_pipeline.job import job_context

ctx = job_context(dbutils, spark)
print(ctx.run_date, ownership.run(ctx))
