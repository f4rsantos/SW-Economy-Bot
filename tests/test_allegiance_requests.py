# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from datetime import datetime, timezone

import pytest

from repositories import allegiance_repo
from services import user_service


def make_request_row(request_id=1, user_id=100, faction_id=7, status="pending"):
    return {
        "id": request_id,
        "user_id": user_id,
        "faction_id": faction_id,
        "status": status,
        "requested_at": datetime.now(timezone.utc),
        "resolved_at": None,
        "resolved_by": None,
    }


async def test_request_supersedes_previous_pending_request(fake_db):
    fake_db.fetchrow_queue.append(make_request_row())
    await allegiance_repo.create_request(100, 7)

    executes = [e for e in fake_db.executed if e[0] == "execute"]
    assert len(executes) == 1
    assert "status = 'denied'" in executes[0][1]
    assert "status = 'pending'" in executes[0][1]


async def test_request_does_not_set_allegiance(fake_db, monkeypatch):
    async def fake_get_user(user_id):
        return object()

    monkeypatch.setattr(user_service, "get_user", fake_get_user)
    fake_db.fetchrow_queue.append(make_request_row())

    await user_service.request_user_allegiance(100, 7)

    updates = [e for e in fake_db.executed if "SET allegiance" in e[1]]
    assert updates == []


async def test_resolve_request_only_touches_pending_rows(fake_db):
    fake_db.fetchrow_queue.append(make_request_row(status="approved"))
    await allegiance_repo.resolve_request(1, "approved", 999)

    query = fake_db.executed[-1][1]
    assert "AND status = 'pending'" in query


async def test_approve_already_resolved_request_raises(fake_db, monkeypatch):
    async def fake_resolve(request_id, status, resolved_by):
        return None

    monkeypatch.setattr(allegiance_repo, "resolve_request", fake_resolve)

    with pytest.raises(ValueError):
        await user_service.approve_allegiance_request(1, 999, "Athena")


async def test_approve_sets_allegiance_to_display_name(fake_db, monkeypatch):
    captured = {}

    async def fake_resolve(request_id, status, resolved_by):
        captured["status"] = status
        return allegiance_repo.AllegianceRequest.from_row(make_request_row())

    async def fake_set(user_id, value):
        captured["user_id"] = user_id
        captured["value"] = value
        return object()

    monkeypatch.setattr(allegiance_repo, "resolve_request", fake_resolve)
    monkeypatch.setattr(user_service, "set_user_allegiance", fake_set)

    await user_service.approve_allegiance_request(1, 999, "Athena")

    assert captured["status"] == "approved"
    assert captured["user_id"] == 100
    assert captured["value"] == "Athena"


async def test_deny_does_not_set_allegiance(fake_db, monkeypatch):
    captured = {}

    async def fake_resolve(request_id, status, resolved_by):
        captured["status"] = status
        return allegiance_repo.AllegianceRequest.from_row(make_request_row(status="denied"))

    async def fake_set(user_id, value):
        captured["set_called"] = True
        return object()

    monkeypatch.setattr(allegiance_repo, "resolve_request", fake_resolve)
    monkeypatch.setattr(user_service, "set_user_allegiance", fake_set)

    await user_service.deny_allegiance_request(1, 999, "Athena")

    assert captured["status"] == "denied"
    assert "set_called" not in captured


async def test_approval_survives_notification_failure(fake_db, monkeypatch):
    captured = {}

    async def fake_resolve(request_id, status, resolved_by):
        return allegiance_repo.AllegianceRequest.from_row(make_request_row())

    async def fake_set(user_id, value):
        captured["value"] = value
        return object()

    monkeypatch.setattr(allegiance_repo, "resolve_request", fake_resolve)
    monkeypatch.setattr(user_service, "set_user_allegiance", fake_set)

    from services import notification_service

    async def boom(*args, **kwargs):
        raise RuntimeError("dm closed")

    monkeypatch.setattr(notification_service, "notify_allegiance_resolved", boom, raising=False)

    await user_service.approve_allegiance_request(1, 999, "Athena")

    assert captured["value"] == "Athena"


async def test_pending_requests_scoped_to_faction(fake_db):
    fake_db.fetch_queue.append([make_request_row(faction_id=7)])
    await allegiance_repo.get_pending_requests_for_faction(7)

    query, args = fake_db.executed[-1][1], fake_db.executed[-1][2]
    assert "status = 'pending'" in query
    assert args == (7,)
