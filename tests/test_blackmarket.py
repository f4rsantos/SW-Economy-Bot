# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import pytest
from services.blackmarket_service import (
    buy_price_for_tier,
    total_buy_price,
    sell_payout,
    ALLOY_HOLD_CAP,
    SELL_PAYOUT_BASE,
    SELL_PAYOUT_MIN_RATIO,
    SELL_PAYOUT_MAX_RATIO,
)


def test_buy_price_for_tier_zero_held():
    assert buy_price_for_tier(0) == 200_000


def test_buy_price_for_tier_one_held():
    assert buy_price_for_tier(1) == 220_000


def test_buy_price_for_tier_two_held():
    assert buy_price_for_tier(2) == 242_000


def test_buy_price_for_tier_nine_held():
    assert buy_price_for_tier(9) == round(200_000 * (1.1 ** 9))


def test_total_buy_price_single_unit_zero_held():
    result = total_buy_price(0, 1)
    assert result == {'CM': 200_000, 'EL': 200_000, 'CS': 200_000}


def test_total_buy_price_two_units_zero_held():
    result = total_buy_price(0, 2)
    expected = 200_000 + 220_000
    assert result == {'CM': expected, 'EL': expected, 'CS': expected}


def test_total_buy_price_spans_tiers_when_already_holding():
    result = total_buy_price(1, 2)
    expected = buy_price_for_tier(1) + buy_price_for_tier(2)
    assert result == {'CM': expected, 'EL': expected, 'CS': expected}


def test_total_buy_price_three_units_from_zero_matches_sum_of_tiers():
    result = total_buy_price(0, 3)
    expected = buy_price_for_tier(0) + buy_price_for_tier(1) + buy_price_for_tier(2)
    assert result['CM'] == expected


def test_alloy_hold_cap_is_ten():
    assert ALLOY_HOLD_CAP == 10


def test_sell_payout_stays_within_band():
    lo = round(SELL_PAYOUT_BASE * SELL_PAYOUT_MIN_RATIO)
    hi = round(SELL_PAYOUT_BASE * SELL_PAYOUT_MAX_RATIO)
    for _ in range(2000):
        payout = sell_payout()
        for res in ('CM', 'EL', 'CS'):
            assert lo <= payout[res] <= hi


def test_sell_payout_same_ratio_across_resources_in_one_roll():
    for _ in range(200):
        payout = sell_payout()
        values = set(payout.values())
        assert len(values) == 1
