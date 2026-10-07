"""Structural checks on databricks.yml (no workspace needed)."""

import tomllib

import yaml

from kiosque_pipeline.cli import steps
from conftest import REPO_ROOT

BUNDLE = yaml.safe_load((REPO_ROOT / "databricks.yml").read_text(encoding="utf-8"))
JOB = BUNDLE["resources"]["jobs"]["kiosque_daily"]
EXPECTED = ["ref", "normalize", "cluster", "ownership", "metrics", "publish"]


def test_tasks_are_chained_in_order():
    tasks = JOB["tasks"]
    assert [t["task_key"] for t in tasks] == EXPECTED
    for previous, task in zip(tasks, tasks[1:]):
        assert task["depends_on"] == [{"task_key": previous["task_key"]}]


def test_every_task_runs_the_wheel_entry_point_for_its_own_step():
    for task in JOB["tasks"]:
        wheel = task["python_wheel_task"]
        assert (wheel["package_name"], wheel["entry_point"]) == ("kiosque_pipeline", "kiosque-step")
        params = wheel["parameters"]
        assert params[params.index("--step") + 1] == task["task_key"]
        assert params[params.index("--run-date") + 1] == "{{job.parameters.run_date}}"
        assert params[params.index("--catalog") + 1] == "{{job.parameters.catalog}}"
        assert params[params.index("--config-dir") + 1] == "{{job.parameters.config_dir}}"
        assert task["task_key"] in steps


def test_entry_point_is_declared_in_the_wheel():
    pyproject = tomllib.loads((REPO_ROOT / "pipeline" / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["scripts"]["kiosque-step"] == "kiosque_pipeline.cli:main"


def test_runs_on_serverless_in_cost_efficient_mode():
    assert "job_clusters" not in JOB
    assert JOB["performance_target"] == "STANDARD"
    for task in JOB["tasks"]:
        assert "job_cluster_key" not in task and "libraries" not in task
        assert task["environment_key"] == "pipeline"


def test_environment_installs_the_wheel_and_the_embedding_model_library():
    [env] = JOB["environments"]
    assert env["environment_key"] == "pipeline"
    assert env["spec"]["environment_version"] == "4"
    assert env["spec"]["dependencies"] == ["./pipeline/dist/*.whl", "sentence-transformers>=2.7"]


def test_scheduled_after_collector_and_alerts_on_failure():
    assert JOB["schedule"]["quartz_cron_expression"] == "0 20 6 * * ?"
    assert JOB["schedule"]["timezone_id"] == "UTC"
    assert JOB["email_notifications"]["on_failure"] == ["${var.alert_email}"]


def test_job_parameters():
    params = {p["name"]: p["default"] for p in JOB["parameters"]}
    assert params == {"run_date": "", "config_dir": "${workspace.file_path}/config", "catalog": "kiosque"}


def test_prod_target_pins_a_shared_root_path():
    # mode: production requires root_path; a shared path lets both a user and
    # the CI service principal deploy the same single copy.
    root_path = BUNDLE["targets"]["prod"]["workspace"]["root_path"]
    assert root_path == "/Workspace/Shared/.bundle/${bundle.name}/${bundle.target}"
