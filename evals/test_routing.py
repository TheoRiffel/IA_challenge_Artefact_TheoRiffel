"""Tier 2 pytest integration — offline tool routing, deterministic, no API key."""

from __future__ import annotations

import pytest

from .cases import CASES
from .routing import run_routing, score


@pytest.fixture(scope="module")
def results():
    return run_routing()


def test_every_case_routes_to_expected_tools(results):
    mismatches = [
        (r.case.id, list(r.case.expected_tools), list(r.called_tools))
        for r in results
        if not r.passed
    ]
    assert not mismatches, f"routing mismatches (id, expected, got): {mismatches}"


def test_offline_routing_is_perfect(results):
    hits, total = score(results)
    assert hits == total, f"only {hits}/{total} cases routed correctly"


def test_dataset_covers_all_scenarios():
    tags = {c.scenario_tag for c in CASES}
    expected = {
        "price", "search", "order", "policy",
        "out_of_scope_accessory", "off_topic",
    }
    assert expected <= tags, f"dataset missing scenarios: {expected - tags}"


def test_out_of_scope_cases_call_no_tool(results):
    for r in results:
        if not r.case.expected_tools:
            assert r.called_tools == (), (
                f"{r.case.id} should call no tool, got {r.called_tools}"
            )
