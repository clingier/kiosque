"""Structural checks on databricks.yml (no workspace needed)."""

import yaml

from conftest import REPO_ROOT

BUNDLE = yaml.safe_load((REPO_ROOT / "databricks.yml").read_text(encoding="utf-8"))
JOB = BUNDLE["resources"]["jobs"]["kiosque_daily"]
EXPECTED = ["normalize", "cluster", "ownership", "metrics", "publish"]


def test_tasks_are_chained_in_order():
    tasks = JOB["tasks"]
    assert [t["task_key"] for t in tasks] == EXPECTED
    for previous, task in zip(tasks, tasks[1:]):
        assert task["depends_on"] == [{"task_key": previous["task_key"]}]


def test_notebooks_exist():
    for task in JOB["tasks"]:
        path = REPO_ROOT / task["notebook_task"]["notebook_path"].removeprefix("./")
        assert path.is_file(), path


def test_scheduled_after_collector_and_alerts_on_failure():
    assert JOB["schedule"]["quartz_cron_expression"] == "0 20 6 * * ?"
    assert JOB["schedule"]["timezone_id"] == "UTC"
    assert JOB["email_notifications"]["on_failure"] == ["${var.alert_email}"]


def test_every_task_installs_the_wheel():
    for task in JOB["tasks"]:
        assert {"whl": "./pipeline/dist/*.whl"} in task["libraries"]


def test_prod_target_pins_a_shared_root_path():
    # mode: production requires root_path; a shared path lets both a user and
    # the CI service principal deploy the same single copy.
    root_path = BUNDLE["targets"]["prod"]["workspace"]["root_path"]
    assert root_path == "/Workspace/Shared/.bundle/${bundle.name}/${bundle.target}"
