# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import pytest
from services.vehicle_service import compute_refit, build_days


def test_cheaper_refit_credits_difference():
    deltas, ratio = compute_refit({"CM": 500, "ER": 999}, {"CM": 1000, "ER": 1})
    by_name = {d["name"]: d["amount"] for d in deltas}
    assert by_name["CM"] == -500
    assert ratio == pytest.approx(0.5)


def test_pricier_refit_charges_difference():
    deltas, ratio = compute_refit({"CM": 2000}, {"CM": 1000})
    by_name = {d["name"]: d["amount"] for d in deltas}
    assert by_name["CM"] == 1000
    assert ratio == pytest.approx(2.0)


def test_ratio_ignores_er_in_totals():
    deltas, ratio = compute_refit({"CM": 1000, "ER": 1_000_000}, {"CM": 1000, "ER": 1})
    by_name = {d["name"]: d["amount"] for d in deltas}
    assert by_name["ER"] == 999_999
    assert "CM" not in by_name
    assert ratio == pytest.approx(1.0)


def test_ratio_clamps_low():
    _, ratio = compute_refit({"CM": 10}, {"CM": 10000})
    assert ratio == pytest.approx(0.1)


def test_ratio_clamps_high():
    _, ratio = compute_refit({"CM": 100000}, {"CM": 10})
    assert ratio == pytest.approx(4.0)


def test_ratio_defaults_to_max_when_old_cost_zero():
    _, ratio = compute_refit({"CM": 100}, {})
    assert ratio == pytest.approx(4.0)


def test_zero_delta_resources_are_omitted():
    deltas, _ = compute_refit({"CM": 1000, "EL": 500}, {"CM": 1000, "EL": 200})
    names = {d["name"] for d in deltas}
    assert "CM" not in names
    assert "EL" in names


def test_full_refit_time_formula():
    deltas, ratio = compute_refit({"CM": 2000}, {"CM": 1000})
    days = build_days(250) * 0.75 * ratio
    assert days == pytest.approx(7.0 * 0.75 * 2.0)
