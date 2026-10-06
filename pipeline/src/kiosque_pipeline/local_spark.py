"""local_spark.py — A local Delta-enabled Spark session for tests and run_pipeline.py."""

import os
import sys
from pathlib import Path

HOMEBREW_JDK = "/opt/homebrew/opt/openjdk@21"
SCHEMAS = ("ref", "bronze", "silver", "gold")


def local_session(warehouse_dir):
    if "JAVA_HOME" not in os.environ and Path(HOMEBREW_JDK).exists():
        os.environ["JAVA_HOME"] = HOMEBREW_JDK
    # Python workers must run the driver's interpreter, not whatever python3 is on PATH.
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    from delta import configure_spark_with_delta_pip
    from pyspark.sql import SparkSession

    builder = (
        SparkSession.builder.master("local[2]")
        .appName("kiosque-local")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.sql.warehouse.dir", str(warehouse_dir))
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
    )
    return configure_spark_with_delta_pip(builder).getOrCreate()


def ensure_schemas(spark, catalog: str = "spark_catalog") -> None:
    for schema in SCHEMAS:
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
