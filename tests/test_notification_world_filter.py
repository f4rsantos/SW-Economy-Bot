# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import pytest

from repositories import notification_repo
from services import notification_service
from tests.test_notification_recipients import make_settings, patched


def with_worlds(mode, ids, **kwargs):
    settings = make_settings(**kwargs)
    settings["world_mode"] = mode
    settings["world_ids"] = tuple(ids)
    return settings


def test_world_allowed_all_mode():
    assert notification_service._world_allowed(with_worlds("all", []), 5)


def test_world_allowed_include_mode():
    settings = with_worlds("include", [5])
    assert notification_service._world_allowed(settings, 5)
    assert not notification_service._world_allowed(settings, 6)


def test_world_allowed_exclude_mode():
    settings = with_worlds("exclude", [5])
    assert not notification_service._world_allowed(settings, 5)
    assert notification_service._world_allowed(settings, 6)


def test_world_allowed_without_world_passes():
    assert notification_service._world_allowed(with_worlds("include", [5]), None)


@pytest.mark.asyncio
async def test_excluded_origin_still_notifies_on_destination(patched):
    patched["leader_rows"][10] = [{"faction_id": 2, "user_id": 200, "is_leader": False, "is_own": False}]
    patched["leader_rows"][20] = [{"faction_id": 2, "user_id": 200, "is_leader": False, "is_own": False}]
    patched["settings"][200] = with_worlds("exclude", [10])

    recipients = await notification_service._collect_recipients(10, 20, 1, notification_service.EVENT_TRANSFER)

    assert 200 in recipients


@pytest.mark.asyncio
async def test_include_mode_skips_unlisted_worlds(patched):
    patched["leader_rows"][10] = [{"faction_id": 2, "user_id": 200, "is_leader": False, "is_own": False}]
    patched["settings"][200] = with_worlds("include", [99])

    recipients = await notification_service._collect_recipients(10, None, 1, notification_service.EVENT_MOVEMENT)

    assert 200 not in recipients


@pytest.mark.asyncio
async def test_fleet_arrival_respects_world_filter(patched):
    patched["faction_recipient_rows"][1] = [{"user_id": 100}]
    patched["settings"][100] = with_worlds("exclude", [7])

    blocked = await notification_service._collect_faction_recipients(1, notification_service.EVENT_FLEET_ARRIVAL, 7)
    allowed = await notification_service._collect_faction_recipients(1, notification_service.EVENT_FLEET_ARRIVAL, 8)

    assert 100 not in blocked
    assert 100 in allowed


@pytest.mark.asyncio
async def test_save_rejects_filter_without_worlds():
    with pytest.raises(ValueError):
        await notification_service.save_notification_settings(1, "dm", None, {}, "include", [])


@pytest.mark.asyncio
async def test_save_clears_worlds_for_all_mode(monkeypatch):
    captured = {}

    async def fake_set(user_id, mode, channel_id, flags, world_mode, world_ids):
        captured.update(mode=mode, channel_id=channel_id, flags=flags, world_mode=world_mode, world_ids=world_ids)
        return object()

    monkeypatch.setattr(notification_repo, "set_user_notify_settings", fake_set)
    await notification_service.save_notification_settings(1, "dm", 123, {"transfers": True}, "all", [4, 5])

    assert captured["world_ids"] == []
    assert captured["channel_id"] is None
    assert captured["flags"]["transfers"] is True
    assert captured["flags"]["battle"] is False
    notification_service.cache_manager.users.pop(1, None)
