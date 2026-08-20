import random
import pytest

FLOOR_SMALL = 250_000
FLOOR_LARGE = 50_000_000_000
from services.casino_service import (
    table_max_for_pool,
    edge_for_pool,
    trim_amount_for_pool,
    RICH_MULTIPLIER,
    EDGE_MIN,
)
from services.casino_games import (
    slot_weights_for_edge,
    spin_reel,
    evaluate_slots,
    SLOT_TRIPLE_PAYOUTS,
    play_roulette,
    ROULETTE_WHEEL_ORDER,
    roulette_color,
    ROULETTE_RED,
    chicken_multiplier_at_step,
    chicken_resolve_step,
    chicken_survival_probability,
    CHICKEN_MAX_STEPS,
    chicken_max_multiplier,
    roulette_animation_frames,
    random_loss_message,
    PIRATE_LOSS_MESSAGES,
)


def test_table_max_at_floor_is_twenty_percent():
    floor = FLOOR_SMALL
    assert table_max_for_pool(floor, floor) == int(floor * 0.20)


def test_table_max_at_rich_is_five_percent():
    floor = FLOOR_SMALL
    rich = floor * RICH_MULTIPLIER
    assert table_max_for_pool(rich, floor) == pytest.approx(int(rich * 0.05), abs=1)


def test_table_max_beyond_rich_stays_clamped_at_five_percent():
    floor = FLOOR_SMALL
    way_rich = floor * RICH_MULTIPLIER * 5
    assert table_max_for_pool(way_rich, floor) == pytest.approx(int(way_rich * 0.05), abs=1)


def test_table_max_midpoint_is_between_bounds():
    floor = FLOOR_SMALL
    mid = floor * (1 + RICH_MULTIPLIER) / 2
    result_pct = table_max_for_pool(mid, floor) / mid
    assert 0.05 < result_pct < 0.20


def test_edge_at_floor_is_twelve_percent():
    floor = FLOOR_LARGE
    assert edge_for_pool(floor, floor) == pytest.approx(0.12)


def test_edge_at_rich_is_four_percent_but_clamped_to_min():
    floor = FLOOR_LARGE
    rich = floor * RICH_MULTIPLIER
    assert edge_for_pool(rich, floor) == pytest.approx(EDGE_MIN)


def test_edge_never_below_min_even_far_beyond_rich():
    floor = FLOOR_LARGE
    huge = floor * RICH_MULTIPLIER * 100
    assert edge_for_pool(huge, floor) >= EDGE_MIN


def test_edge_never_above_twelve_percent_below_floor():
    floor = FLOOR_LARGE
    below = floor * 0.5
    assert edge_for_pool(below, floor) <= 0.12


def test_edge_is_monotonic_decreasing_with_pool_health():
    floor = FLOOR_LARGE
    edges = [edge_for_pool(floor * m, floor) for m in [1, 2, 4, 6, 8, 10]]
    assert edges == sorted(edges, reverse=True)


def test_trim_zero_below_threshold():
    floor = FLOOR_SMALL
    assert trim_amount_for_pool(floor * 2, floor) == 0


def test_trim_zero_at_threshold():
    floor = FLOOR_SMALL
    assert trim_amount_for_pool(floor * 3, floor) == 0


def test_trim_quarter_of_excess_above_threshold():
    floor = FLOOR_SMALL
    pool = floor * 3 + 400_000
    expected = int(400_000 * 0.25)
    assert trim_amount_for_pool(pool, floor) == expected


def test_slots_rtp_matches_configured_edge():
    random.seed(1234)
    for edge in (0.05, 0.08, 0.12):
        weights = slot_weights_for_edge(edge)
        n = 60_000
        total_payout = 0.0
        for _ in range(n):
            reels = [spin_reel(weights) for _ in range(3)]
            total_payout += evaluate_slots(reels)
        rtp = total_payout / n
        assert abs(rtp - (1 - edge)) < 0.03


def test_slots_payout_never_exceeds_max_triple_payout():
    weights = slot_weights_for_edge(0.05)
    max_payout = max(SLOT_TRIPLE_PAYOUTS.values())
    for _ in range(2000):
        reels = [spin_reel(weights) for _ in range(3)]
        assert evaluate_slots(reels) <= max_payout


def test_roulette_wheel_has_37_pockets():
    assert len(ROULETTE_WHEEL_ORDER) == 37
    assert sorted(ROULETTE_WHEEL_ORDER) == list(range(37))


def test_roulette_color_counts():
    reds = sum(1 for p in range(1, 37) if roulette_color(p) == 'RED')
    blacks = sum(1 for p in range(1, 37) if roulette_color(p) == 'BLACK')
    assert reds == 18
    assert blacks == 18
    assert roulette_color(0) == 'GREEN'


def test_roulette_rtp_matches_configured_edge_red():
    random.seed(99)
    for edge in (0.05, 0.08, 0.12):
        n = 60_000
        total_payout = 0.0
        for _ in range(n):
            r = play_roulette('red', None, edge)
            total_payout += r['multiplier']
        rtp = total_payout / n
        assert abs(rtp - (1 - edge)) < 0.03


def test_roulette_rtp_matches_configured_edge_straight():
    random.seed(77)
    for edge in (0.05, 0.08, 0.12):
        n = 60_000
        total_payout = 0.0
        for _ in range(n):
            r = play_roulette('straight', 17, edge)
            total_payout += r['multiplier']
        rtp = total_payout / n
        assert abs(rtp - (1 - edge)) < 0.05


def test_roulette_animation_frames_land_on_final_pocket():
    frames = roulette_animation_frames(23)
    assert frames[-1][2] == 23


def test_chicken_step_one_multiplier_stays_at_or_above_one_at_max_edge():
    assert chicken_multiplier_at_step(1, 0.12) >= 1.0


def test_chicken_multiplier_grows_with_each_step():
    edge = 0.08
    multipliers = [chicken_multiplier_at_step(s, edge) for s in range(0, CHICKEN_MAX_STEPS + 1)]
    assert multipliers == sorted(multipliers)


def test_chicken_max_multiplier_is_finite_and_positive():
    for edge in (0.05, 0.08, 0.12):
        m = chicken_max_multiplier(edge)
        assert m > 1.0


def test_chicken_rtp_matches_configured_edge_across_strategies():
    random.seed(2024)

    def simulate(edge, target_step, n=40_000):
        total_payout = 0.0
        for _ in range(n):
            step = 0
            alive = True
            while alive and step < target_step:
                if chicken_resolve_step(step + 1):
                    step += 1
                else:
                    alive = False
            if alive:
                total_payout += chicken_multiplier_at_step(step, edge) if step > 0 else 0.0
        return total_payout / n

    for edge in (0.05, 0.08, 0.12):
        for target_step in (1, 3, 5, CHICKEN_MAX_STEPS):
            rtp = simulate(edge, target_step)
            assert abs(rtp - (1 - edge)) < 0.05


def test_chicken_survival_probability_decreases_with_step():
    probs = [chicken_survival_probability(s) for s in range(1, CHICKEN_MAX_STEPS + 1)]
    assert probs == sorted(probs, reverse=True)


def test_loss_message_pool_has_variety():
    assert len(PIRATE_LOSS_MESSAGES) >= 15
    assert len(set(PIRATE_LOSS_MESSAGES)) == len(PIRATE_LOSS_MESSAGES)


def test_loss_message_returns_from_pool():
    for _ in range(50):
        assert random_loss_message() in PIRATE_LOSS_MESSAGES
