# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from decimal import Decimal

import pytest

from dtos.national_spirit import NationalSpirit
from services import income_executor


@pytest.mark.asyncio
async def test_world_trade_skips_treasury_resources(monkeypatch):
    trades = [{
        'id': 1, 'receiver_faction_id': 2, 'sender_world_id': None, 'receiver_world_id': 50,
        'escort_fleet_id': None, 'amount': 1000, 'resource_name': 'ER', 'resource_id': 9,
    }]

    async def fake_trades(faction_id):
        return trades

    async def fake_names():
        return {10: "A", 50: "B"}

    async def fake_dest(ids):
        return {}

    monkeypatch.setattr(income_executor, "fetch_all_trade_deals", fake_trades)
    monkeypatch.setattr(income_executor, "fetch_all_world_names", fake_names)
    monkeypatch.setattr(income_executor, "fetch_best_destination_worlds", fake_dest)

    world_resources = {10: {'ER': 5000}}
    _, transfers = await income_executor._process_trade_deals(1, world_resources, {}, set())

    assert transfers == []
    assert world_resources[10]['ER'] == 5000


@pytest.mark.asyncio
async def test_apply_treasury_trades_moves_each_trade(monkeypatch):
    calls = []

    async def fake_transfer(from_id, to_id, resource_id, amount):
        calls.append((from_id, to_id, resource_id, amount))
        return amount // 2

    monkeypatch.setattr(income_executor, "transfer_treasury_resource", fake_transfer)
    await income_executor._apply_treasury_trades(1, [
        {'id': 1, 'receiver_faction_id': 2, 'resource_id': 9, 'resource_name': 'ER', 'amount': 3_000_000_000},
    ])

    assert calls == [(1, 2, 9, 3_000_000_000)]


def test_national_spirit_modifier_is_float():
    spirit = NationalSpirit.from_row({
        "display_name": "X", "effect_type": "efficiency", "modifier_value": Decimal("0.05"),
        "granted_at": None, "expires_at": None,
    })
    assert isinstance(spirit.modifier_value, float)
    assert 0.5 + spirit.modifier_value == pytest.approx(0.55)
