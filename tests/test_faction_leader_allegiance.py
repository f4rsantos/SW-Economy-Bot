# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import pytest

from services import faction_service
from repositories import allegiance_repo


class FakeFaction:
    def __init__(self, id=1, display_name="Athena"):
        self.id = id
        self.display_name = display_name


async def test_set_leader_allegiance_calls_set_user_allegiance(monkeypatch):
    captured = {}

    async def fake_get_pending(user_id):
        return None

    async def fake_set_user_allegiance(user_id, value):
        captured["user_id"] = user_id
        captured["value"] = value
        return object()

    monkeypatch.setattr(allegiance_repo, "get_pending_request_for_user", fake_get_pending)
    monkeypatch.setattr("services.user_service.set_user_allegiance", fake_set_user_allegiance)

    await faction_service._set_leader_allegiance(1, "Athena", 100)

    assert captured["user_id"] == 100
    assert captured["value"] == "Athena"


async def test_set_leader_allegiance_resolves_own_pending_request(monkeypatch):
    captured = {}

    class FakeRequest:
        id = 42

    async def fake_get_pending(user_id):
        return FakeRequest()

    async def fake_resolve(request_id, status, resolved_by):
        captured["request_id"] = request_id
        captured["status"] = status
        captured["resolved_by"] = resolved_by
        return None

    async def fake_set_user_allegiance(user_id, value):
        return object()

    monkeypatch.setattr(allegiance_repo, "get_pending_request_for_user", fake_get_pending)
    monkeypatch.setattr(allegiance_repo, "resolve_request", fake_resolve)
    monkeypatch.setattr("services.user_service.set_user_allegiance", fake_set_user_allegiance)

    await faction_service._set_leader_allegiance(1, "Athena", 100)

    assert captured["request_id"] == 42
    assert captured["status"] == "approved"
    assert captured["resolved_by"] == 100


async def test_set_leader_allegiance_failure_does_not_raise(monkeypatch):
    async def boom(user_id):
        raise RuntimeError("db exploded")

    monkeypatch.setattr(allegiance_repo, "get_pending_request_for_user", boom)

    await faction_service._set_leader_allegiance(1, "Athena", 100)


async def test_create_faction_in_db_sets_leader_allegiance(monkeypatch):
    captured = {}
    faction = FakeFaction(id=5, display_name="Solaris Combine")

    async def fake_insert_faction(*args, **kwargs):
        return faction

    async def fake_set_leader_allegiance(faction_id, faction_display_name, leader_id):
        captured["faction_id"] = faction_id
        captured["faction_display_name"] = faction_display_name
        captured["leader_id"] = leader_id

    monkeypatch.setattr(faction_service.faction_repo, "insert_faction", fake_insert_faction)
    monkeypatch.setattr(faction_service, "_set_leader_allegiance", fake_set_leader_allegiance)

    await faction_service.create_faction_in_db(
        conn=object(), name="solaris", formal_name="Solaris Combine", color="#ffffff",
        leader_name="Leader", flag="", leader_id=200, faction_type=0, starting_world_id=None,
    )

    assert captured["faction_id"] == 5
    assert captured["faction_display_name"] == "Solaris Combine"
    assert captured["leader_id"] == 200


async def test_create_faction_in_db_succeeds_when_allegiance_set_fails(monkeypatch):
    faction = FakeFaction(id=6, display_name="Nova Republic")

    async def fake_insert_faction(*args, **kwargs):
        return faction

    async def boom(faction_id, faction_display_name, leader_id):
        raise RuntimeError("should never propagate, but simulate defensive test anyway")

    monkeypatch.setattr(faction_service.faction_repo, "insert_faction", fake_insert_faction)

    async def fake_get_pending(user_id):
        raise RuntimeError("allegiance backend down")

    monkeypatch.setattr(allegiance_repo, "get_pending_request_for_user", fake_get_pending)

    result = await faction_service.create_faction_in_db(
        conn=object(), name="nova", formal_name="Nova Republic", color="#ffffff",
        leader_name="Leader", flag="", leader_id=300, faction_type=1, starting_world_id=None,
    )

    assert result is faction
