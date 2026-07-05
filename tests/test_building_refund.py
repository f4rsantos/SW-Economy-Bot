import pytest
from services.building_service import _calculate_building_cost, _calculate_refund


@pytest.mark.parametrize("existing_actual,amount,level", [
    (30, 1, 1),
    (30, 3, 1),
    (27, 1, 1),
    (28, 5, 2),
    (100, 10, 3),
])
def test_refund_matches_buy_cost_at_100_percent(existing_actual, amount, level):
    base_costs = {"CM": 100, "EL": 40}
    scaling_before = max(0, existing_actual - 27)
    cost = _calculate_building_cost(base_costs, scaling_before, amount, level, building_id=1)

    scaling_after = max(0, (existing_actual + amount) - 27)
    refund = _calculate_refund(base_costs, scaling_after, amount, level, week=True, building_id=1)

    assert refund == cost


def test_refund_at_30_percent_is_less_than_cost():
    base_costs = {"CM": 100}
    scaling_before = 10
    cost = _calculate_building_cost(base_costs, scaling_before, 5, 1, building_id=1)
    scaling_after = scaling_before + 5
    refund = _calculate_refund(base_costs, scaling_after, 5, 1, week=False, building_id=1)
    assert refund["CM"] < cost["CM"]
    assert refund["CM"] == pytest.approx(cost["CM"] * 0.3, abs=1)


def test_refund_never_exceeds_original_cost_at_full_rate():
    base_costs = {"CM": 250, "EL": 90, "CS": 15}
    for existing_actual in [0, 5, 27, 50, 200]:
        for amount in [1, 2, 7]:
            scaling_before = max(0, existing_actual - 27)
            cost = _calculate_building_cost(base_costs, scaling_before, amount, 1, building_id=1)
            scaling_after = max(0, (existing_actual + amount) - 27)
            refund = _calculate_refund(base_costs, scaling_after, amount, 1, week=True, building_id=1)
            for resource in base_costs:
                assert refund[resource] <= cost[resource]
