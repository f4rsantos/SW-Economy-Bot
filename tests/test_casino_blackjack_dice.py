# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import random
import pytest

from utils.casino_games import (
    roll_die,
    dice_payout_multiplier,
    dice_max_multiplier,
    dice_roll_animation_frames,
    DICE_HIGH,
    DICE_LOW,
    draw_blackjack_card,
    blackjack_hand_value,
    blackjack_is_soft,
    blackjack_is_natural,
    blackjack_dealer_should_hit,
    blackjack_resolve,
    blackjack_win_multiplier,
    blackjack_natural_multiplier,
    blackjack_max_multiplier,
    CARD_RANK_VALUES,
)
from services import casino_service
from repositories import casino_repo


def test_dice_high_low_rtp_matches_configured_edge():
    random.seed(11)
    for edge in (0.05, 0.08, 0.12):
        n = 60_000
        total_payout = 0.0
        for _ in range(n):
            roll = roll_die()
            multiplier = dice_payout_multiplier('high', None, roll, edge)
            total_payout += multiplier
        rtp = total_payout / n
        assert abs(rtp - (1 - edge)) < 0.02


def test_dice_exact_rtp_matches_configured_edge():
    random.seed(12)
    for edge in (0.05, 0.08, 0.12):
        n = 60_000
        total_payout = 0.0
        for _ in range(n):
            roll = roll_die()
            multiplier = dice_payout_multiplier('exact', 4, roll, edge)
            total_payout += multiplier
        rtp = total_payout / n
        assert abs(rtp - (1 - edge)) < 0.02


def test_dice_high_low_partition_covers_all_faces_without_overlap():
    assert DICE_HIGH | DICE_LOW == {1, 2, 3, 4, 5, 6}
    assert DICE_HIGH & DICE_LOW == set()


def test_dice_unknown_bet_type_raises():
    with pytest.raises(ValueError):
        dice_payout_multiplier('sideways', None, 3, 0.05)


def test_dice_max_multiplier_matches_exact_fair_multiplier():
    assert dice_max_multiplier() == 6.0


def test_dice_animation_lands_on_final_roll():
    frames = dice_roll_animation_frames(5)
    assert frames[-1] == 5
    assert len(frames) == 4


def test_blackjack_hand_value_counts_ace_as_eleven_or_one():
    assert blackjack_hand_value([('A', '♠'), ('K', '♥')]) == 21
    assert blackjack_hand_value([('A', '♠'), ('A', '♥'), ('9', '♦')]) == 21
    assert blackjack_hand_value([('A', '♠'), ('A', '♥'), ('A', '♦'), ('9', '♣')]) == 12


def test_blackjack_is_soft_detects_usable_ace():
    assert blackjack_is_soft([('A', '♠'), ('6', '♥')]) is True
    assert blackjack_is_soft([('A', '♠'), ('6', '♥'), ('10', '♦')]) is False


def test_blackjack_is_natural_only_on_two_card_twenty_one():
    assert blackjack_is_natural([('A', '♠'), ('K', '♥')]) is True
    assert blackjack_is_natural([('7', '♠'), ('7', '♥'), ('7', '♦')]) is False
    assert blackjack_is_natural([('A', '♠'), ('9', '♥')]) is False


def test_blackjack_dealer_hits_below_seventeen_and_stands_at_or_above():
    assert blackjack_dealer_should_hit([('5', '♠'), ('5', '♥')]) is True
    assert blackjack_dealer_should_hit([('10', '♠'), ('7', '♥')]) is False
    assert blackjack_dealer_should_hit([('10', '♠'), ('7', '♥'), ('2', '♦')]) is False


def test_blackjack_win_multiplier_scales_fair_odds_by_edge():
    for edge in (0.05, 0.08, 0.12):
        assert blackjack_win_multiplier(edge) == pytest.approx(2.0 * (1 - edge))
        assert blackjack_natural_multiplier(edge) == pytest.approx(2.5 * (1 - edge))


def test_blackjack_edge_below_current_casino_floor_still_reduces_multiplier_relative_to_fair():
    assert blackjack_win_multiplier(0.12) < blackjack_win_multiplier(0.05) < 2.0
    assert blackjack_natural_multiplier(0.12) < blackjack_natural_multiplier(0.05) < 2.5


def test_blackjack_max_multiplier_is_natural_fair_multiplier():
    assert blackjack_max_multiplier() == 2.5


def test_blackjack_resolve_bust_player_over_21():
    player = [('10', '♠'), ('9', '♥'), ('5', '♦')]
    dealer = [('10', '♠'), ('7', '♥')]
    result = blackjack_resolve(player, dealer, 0.08)
    assert result['outcome'] == 'bust'
    assert result['multiplier'] == 0.0


def test_blackjack_resolve_dealer_bust_pays_win_multiplier():
    player = [('10', '♠'), ('8', '♥')]
    dealer = [('10', '♠'), ('9', '♥'), ('5', '♦')]
    result = blackjack_resolve(player, dealer, 0.08)
    assert result['outcome'] == 'dealer_bust'
    assert result['multiplier'] == pytest.approx(blackjack_win_multiplier(0.08))


def test_blackjack_resolve_push_on_equal_values():
    player = [('10', '♠'), ('8', '♥')]
    dealer = [('9', '♠'), ('9', '♥')]
    result = blackjack_resolve(player, dealer, 0.08)
    assert result['outcome'] == 'push'
    assert result['multiplier'] == 1.0


def test_blackjack_resolve_loss_when_dealer_beats_player():
    player = [('9', '♠'), ('8', '♥')]
    dealer = [('10', '♠'), ('9', '♥')]
    result = blackjack_resolve(player, dealer, 0.08)
    assert result['outcome'] == 'loss'
    assert result['multiplier'] == 0.0


def test_blackjack_resolve_win_when_player_beats_dealer_without_bust():
    player = [('10', '♠'), ('9', '♥')]
    dealer = [('10', '♠'), ('8', '♥')]
    result = blackjack_resolve(player, dealer, 0.08)
    assert result['outcome'] == 'win'
    assert result['multiplier'] == pytest.approx(blackjack_win_multiplier(0.08))


def _basic_strategy_should_hit(hand, dealer_up):
    value = blackjack_hand_value(hand)
    soft = blackjack_is_soft(hand)
    if soft:
        if value <= 17:
            return True
        if value == 18:
            return dealer_up in (9, 10, 11)
        return False
    if value <= 11:
        return True
    if value == 12:
        return dealer_up in (2, 3, 7, 8, 9, 10, 11)
    if 13 <= value <= 16:
        return dealer_up in (7, 8, 9, 10, 11)
    return False


def test_blackjack_rtp_stays_below_fair_by_roughly_the_configured_edge():
    random.seed(2024)
    n = 40_000
    for edge in (0.05, 0.08, 0.12):
        total_payout = 0.0
        for _ in range(n):
            player = [draw_blackjack_card(), draw_blackjack_card()]
            dealer = [draw_blackjack_card(), draw_blackjack_card()]
            dealer_up = CARD_RANK_VALUES[dealer[0][0]]

            if blackjack_is_natural(player) or blackjack_is_natural(dealer):
                if blackjack_is_natural(player) and blackjack_is_natural(dealer):
                    total_payout += 1.0
                elif blackjack_is_natural(player):
                    total_payout += blackjack_natural_multiplier(edge)
                continue

            busted = False
            while _basic_strategy_should_hit(player, dealer_up):
                player.append(draw_blackjack_card())
                if blackjack_hand_value(player) > 21:
                    busted = True
                    break
            if busted:
                continue

            while blackjack_dealer_should_hit(dealer):
                dealer.append(draw_blackjack_card())

            result = blackjack_resolve(player, dealer, edge)
            total_payout += result['multiplier']

        rtp = total_payout / n
        assert rtp < 1.0 - edge + 0.05
        assert rtp > 1.0 - edge - 0.10


class FakeConn:
    def __init__(self, pool_amount, floor, faction_amount):
        self.pool = pool_amount
        self.floor = floor
        self.faction = faction_amount
        self.res_id = 7

    async def fetchval(self, query, *args):
        if "FROM resources WHERE name" in query:
            return self.res_id
        return self.faction

    async def fetchrow(self, query, *args):
        if "casino_pool" in query:
            return {'resource_id': self.res_id, 'amount': self.pool, 'floor_amount': self.floor}
        return None

    async def execute(self, query, *args):
        if "casino_pool SET amount = amount +" in query:
            self.pool += args[1]
        elif "casino_pool SET amount = amount -" in query:
            self.pool -= args[1]
        elif "faction_treasury SET amount = amount -" in query:
            self.faction -= args[2]
        elif "INSERT INTO faction_treasury" in query:
            self.faction += args[2]


class FakeDB:
    def __init__(self, conn):
        self.conn = conn

    def get_connection(self):
        conn = self.conn

        class Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *a):
                return False

        return Ctx()


class FakeTx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


def _install(monkeypatch, conn):
    conn.transaction = lambda: FakeTx()
    monkeypatch.setattr(casino_repo, 'db', FakeDB(conn))


@pytest.mark.asyncio
async def test_blackjack_open_then_win_close_conserves_value(monkeypatch):
    conn = FakeConn(pool_amount=10_000_000, floor=1_000_000, faction_amount=1_000_000)
    _install(monkeypatch, conn)
    before_total = conn.pool + conn.faction

    opened = await casino_service.open_blackjack_round(1, None, 'ER', 1000)
    assert conn.pool == 10_000_000 + 1000

    await casino_service.close_blackjack_round(1, None, 'ER', opened['res_id'], 1000, 2.0)
    after_total = conn.pool + conn.faction
    assert after_total == before_total


@pytest.mark.asyncio
async def test_blackjack_open_then_loss_close_conserves_value(monkeypatch):
    conn = FakeConn(pool_amount=10_000_000, floor=1_000_000, faction_amount=1_000_000)
    _install(monkeypatch, conn)
    before_total = conn.pool + conn.faction

    opened = await casino_service.open_blackjack_round(1, None, 'ER', 1000)
    await casino_service.close_blackjack_round(1, None, 'ER', opened['res_id'], 1000, 0.0)

    after_total = conn.pool + conn.faction
    assert after_total == before_total
    assert conn.pool == 10_000_000 + 1000


@pytest.mark.asyncio
async def test_blackjack_open_then_push_close_is_neutral(monkeypatch):
    conn = FakeConn(pool_amount=10_000_000, floor=1_000_000, faction_amount=1_000_000)
    _install(monkeypatch, conn)
    pool_before, faction_before = conn.pool, conn.faction

    opened = await casino_service.open_blackjack_round(1, None, 'ER', 1000)
    await casino_service.close_blackjack_round(1, None, 'ER', opened['res_id'], 1000, 1.0)

    assert conn.pool == pool_before
    assert conn.faction == faction_before


@pytest.mark.asyncio
async def test_blackjack_open_then_natural_close_conserves_value(monkeypatch):
    conn = FakeConn(pool_amount=10_000_000, floor=1_000_000, faction_amount=1_000_000)
    _install(monkeypatch, conn)
    before_total = conn.pool + conn.faction

    opened = await casino_service.open_blackjack_round(1, None, 'ER', 1000)
    natural_multiplier = blackjack_natural_multiplier(opened['edge'])
    await casino_service.close_blackjack_round(1, None, 'ER', opened['res_id'], 1000, natural_multiplier)

    after_total = conn.pool + conn.faction
    assert after_total == before_total


@pytest.mark.asyncio
async def test_blackjack_timeout_path_resolves_same_as_stand(monkeypatch):
    conn = FakeConn(pool_amount=10_000_000, floor=1_000_000, faction_amount=1_000_000)
    _install(monkeypatch, conn)
    before_total = conn.pool + conn.faction

    opened = await casino_service.open_blackjack_round(1, None, 'ER', 1000)

    player = [('10', '♠'), ('8', '♥')]
    dealer = [('10', '♠'), ('6', '♥')]
    while blackjack_dealer_should_hit(dealer):
        dealer.append(draw_blackjack_card())
    resolution = blackjack_resolve(player, dealer, opened['edge'])

    await casino_service.close_blackjack_round(1, None, 'ER', opened['res_id'], 1000, resolution['multiplier'])

    after_total = conn.pool + conn.faction
    assert after_total == before_total
