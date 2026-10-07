import pytest

from kiosque_pipeline import cli
from conftest import REPO_ROOT

ARGS = ["--run-date", "2026-10-01", "--catalog", "kiosque", "--config-dir", str(REPO_ROOT / "config")]


class FakeSpark:
    def __init__(self):
        self.conf = self
        self.values = {}

    def set(self, key, value):
        self.values[key] = value


def no_secret(scope, key):
    pytest.fail("no secret expected")


def test_parse_args_requires_a_known_step():
    with pytest.raises(SystemExit):
        cli.parse_args(["--step", "sing", *ARGS])
    assert cli.parse_args(["--step", "cluster", *ARGS]).step == "cluster"


def test_empty_run_date_means_today():
    assert cli.parse_args(["--step", "ref", "--run-date", "", "--catalog", "kiosque", "--config-dir", "x"]).run_date == ""


def test_build_context_for_a_non_publish_step():
    spark = FakeSpark()
    ctx = cli.build_context(cli.parse_args(["--step", "normalize", *ARGS]), spark, no_secret)
    assert (ctx.run_date, ctx.catalog, ctx.raw_root) == ("2026-10-01", "kiosque", "/Volumes/kiosque/raw/feeds")
    assert ctx.storage is None and ctx.spark is spark
    assert spark.values["spark.sql.session.timeZone"] == "UTC"
    assert len(ctx.sources) >= 60 and len(ctx.major_groups) == 6


def test_build_context_for_publish_reads_the_secret(monkeypatch):
    seen = {}

    def secret(scope, key):
        seen["call"] = (scope, key)
        return "conn-string"

    monkeypatch.setattr(cli, "BlobStorage", lambda conn: ("blob", conn))
    ctx = cli.build_context(cli.parse_args(["--step", "publish", *ARGS]), FakeSpark(), secret)
    assert ctx.storage == ("blob", "conn-string")
    assert seen["call"] == ("kiosque", "datalake-connection-string")


def test_main_dispatches_to_the_step(monkeypatch):
    calls = []
    monkeypatch.setattr(cli.steps["ownership"], "run", lambda ctx: calls.append(ctx.run_date) or {"stories": 3})
    result = cli.main(["--step", "ownership", *ARGS], spark=FakeSpark(), get_secret=no_secret)
    assert result == {"stories": 3} and calls == ["2026-10-01"]


def test_cluster_step_gets_the_embedder_factory(monkeypatch):
    seen = {}

    def fake_run(ctx, embedder_factory):
        seen["factory"] = embedder_factory
        return {"stories": 0}

    monkeypatch.setattr(cli.steps["cluster"], "run", fake_run)
    cli.main(["--step", "cluster", *ARGS], spark=FakeSpark(), get_secret=no_secret)
    assert seen["factory"] is cli.SentenceTransformerEmbedder
