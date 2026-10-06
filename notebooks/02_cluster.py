# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Cluster (bronze.articles → silver.stories)
# MAGIC Embeds headlines and groups them into stories covered by ≥ 2 media.

# COMMAND ----------

dbutils.widgets.text("run_date", "")
dbutils.widgets.text("config_dir", "")
dbutils.widgets.text("catalog", "kiosque")

# COMMAND ----------

from kiosque_pipeline.steps import cluster
from kiosque_pipeline.embed import SentenceTransformerEmbedder
from kiosque_pipeline.job import job_context

ctx = job_context(dbutils, spark)
print(ctx.run_date, cluster.run(ctx, SentenceTransformerEmbedder))
