"""Tests for host.json — settings the monitoring alerts depend on."""

import json
from pathlib import Path

HOST = json.loads((Path(__file__).parent.parent / "host.json").read_text(encoding="utf-8"))


def test_successful_invocations_reach_requests_table():
    # The "collector did not run" alert counts collect_feeds rows in `requests`;
    # Host.Results at Error would only log failed invocations.
    assert HOST["logging"]["logLevel"]["Host.Results"] == "Information"


def test_timeout_is_consumption_plan_maximum():
    assert HOST["functionTimeout"] == "00:10:00"
