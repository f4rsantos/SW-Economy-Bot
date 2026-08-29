# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import pytest

from repositories import notification_repo
from services import notification_service


def make_settings(
    mode="dm",
    transfers=True,
    movements=True,
    origin=True,
    destination=True,
    own=False,
    recruitment=True,
    fleet_arrival=True,
    battle=True,
    income=True,
):
    return {
        "mode": mode,
        "channel_id": None,
        "transfers": transfers,
        "movements": movements,
        "origin": origin,
        "destination": destination,
        "own": own,
        "recruitment": recruitment,
        "fleet_arrival": fleet_arrival,
        "battle": battle,
        "income": income,
    }


@pytest.fixture
def patched(monkeypatch):
    state = {
        "leader_rows": {},
        "partner_rows": {},
        "settings": {},
        "faction_recipient_rows": {},
    }

    async def fake_get_interested_leader_rows(world_id, acting_faction_id):
        return state["leader_rows"].get(world_id, [])

    async def fake_get_foreign_sharing_partner_leader_ids(faction_id, exclude_leader_id):
        rows = state["partner_rows"].get(faction_id, [])
        return [r for r in rows if r["leader_id"] != exclude_leader_id]

    async def fake_get_user_notification_settings(user_id):
        return state["settings"].get(user_id, make_settings(mode="off"))

    async def fake_get_faction_recipient_rows(faction_id):
        return state["faction_recipient_rows"].get(faction_id, [])

    monkeypatch.setattr(notification_repo, "get_interested_leader_rows", fake_get_interested_leader_rows)
    monkeypatch.setattr(
        notification_repo, "get_foreign_sharing_partner_leader_ids", fake_get_foreign_sharing_partner_leader_ids
    )
    monkeypatch.setattr(notification_service, "get_user_notification_settings", fake_get_user_notification_settings)
    monkeypatch.setattr(notification_repo, "get_faction_recipient_rows", fake_get_faction_recipient_rows)
    return state


@pytest.mark.asyncio
async def test_own_activity_off_means_no_self_notification(patched):
    patched["leader_rows"][10] = [
        {"faction_id": 1, "user_id": 100, "is_leader": True, "is_own": True}
    ]
    patched["settings"][100] = make_settings(own=False)

    recipients = await notification_service._collect_recipients(10, None, 1, notification_service.EVENT_TRANSFER)

    assert 100 not in recipients


@pytest.mark.asyncio
async def test_own_activity_on_means_self_notification(patched):
    patched["leader_rows"][10] = [
        {"faction_id": 1, "user_id": 100, "is_leader": True, "is_own": True}
    ]
    patched["settings"][100] = make_settings(own=True)

    recipients = await notification_service._collect_recipients(10, None, 1, notification_service.EVENT_TRANSFER)

    assert 100 in recipients
    settings, is_own = recipients[100]
    assert is_own is True


@pytest.mark.asyncio
async def test_foreign_activity_still_reaches_presence_holder(patched):
    patched["leader_rows"][10] = [
        {"faction_id": 2, "user_id": 200, "is_leader": True, "is_own": False}
    ]
    patched["settings"][200] = make_settings(own=False)

    recipients = await notification_service._collect_recipients(10, None, 1, notification_service.EVENT_TRANSFER)

    assert 200 in recipients
    settings, is_own = recipients[200]
    assert is_own is False


@pytest.mark.asyncio
async def test_no_duplicate_recipients_between_presence_and_partner(patched):
    patched["leader_rows"][10] = [
        {"faction_id": 2, "user_id": 200, "is_leader": True, "is_own": False}
    ]
    patched["settings"][200] = make_settings(own=False)
    patched["partner_rows"][2] = [{"faction_id": 3, "leader_id": 200}]

    recipients = await notification_service._collect_recipients(10, None, 1, notification_service.EVENT_TRANSFER)

    assert list(recipients.keys()).count(200) == 1
    assert len(recipients) == 1


@pytest.mark.asyncio
async def test_sharing_partner_receives_alert_once(patched):
    patched["leader_rows"][10] = [
        {"faction_id": 2, "user_id": 200, "is_leader": True, "is_own": False}
    ]
    patched["settings"][200] = make_settings(own=False)
    patched["settings"][300] = make_settings(own=False)
    patched["partner_rows"][2] = [{"faction_id": 3, "leader_id": 300}]

    recipients = await notification_service._collect_recipients(10, None, 1, notification_service.EVENT_TRANSFER)

    assert 200 in recipients and 300 in recipients
    assert len(recipients) == 2


@pytest.mark.asyncio
async def test_own_faction_presence_does_not_reach_sharing_partners(patched):
    patched["leader_rows"][10] = [
        {"faction_id": 1, "user_id": 100, "is_leader": True, "is_own": True}
    ]
    patched["settings"][100] = make_settings(own=True)
    patched["partner_rows"][1] = [{"faction_id": 9, "leader_id": 900}]

    recipients = await notification_service._collect_recipients(10, None, 1, notification_service.EVENT_TRANSFER)

    assert 900 not in recipients


@pytest.mark.parametrize(
    "event_type",
    [
        notification_service.EVENT_RECRUITMENT,
        notification_service.EVENT_FLEET_ARRIVAL,
        notification_service.EVENT_BATTLE,
        notification_service.EVENT_INCOME,
    ],
)
@pytest.mark.asyncio
async def test_new_events_never_reach_non_owner(patched, event_type):
    patched["leader_rows"][10] = [
        {"faction_id": 2, "user_id": 200, "is_leader": True, "is_own": False}
    ]
    patched["settings"][200] = make_settings(own=True)

    recipients = await notification_service._collect_recipients(10, None, 1, event_type)

    assert 200 not in recipients


@pytest.mark.parametrize(
    "event_type",
    [
        notification_service.EVENT_RECRUITMENT,
        notification_service.EVENT_FLEET_ARRIVAL,
        notification_service.EVENT_BATTLE,
        notification_service.EVENT_INCOME,
    ],
)
@pytest.mark.asyncio
async def test_new_events_reach_owner(patched, event_type):
    patched["leader_rows"][10] = [
        {"faction_id": 1, "user_id": 100, "is_leader": True, "is_own": True}
    ]
    patched["settings"][100] = make_settings(own=False)

    recipients = await notification_service._collect_recipients(10, None, 1, event_type)

    assert 100 in recipients


@pytest.mark.asyncio
async def test_new_event_respects_its_own_toggle(patched):
    patched["leader_rows"][10] = [
        {"faction_id": 1, "user_id": 100, "is_leader": True, "is_own": True}
    ]
    patched["settings"][100] = make_settings(recruitment=False)

    recipients = await notification_service._collect_recipients(
        10, None, 1, notification_service.EVENT_RECRUITMENT
    )

    assert 100 not in recipients


@pytest.mark.asyncio
async def test_collect_faction_recipients_off_when_notify_own_but_not_gating(patched):
    patched["faction_recipient_rows"][1] = [
        {"faction_id": 1, "user_id": 100, "is_leader": True}
    ]
    patched["settings"][100] = make_settings(battle=True)

    recipients = await notification_service._collect_faction_recipients(1, notification_service.EVENT_BATTLE)

    assert 100 in recipients


@pytest.mark.asyncio
async def test_collect_faction_recipients_respects_mode_off(patched):
    patched["faction_recipient_rows"][1] = [
        {"faction_id": 1, "user_id": 100, "is_leader": True}
    ]
    patched["settings"][100] = make_settings(mode="off", battle=True)

    recipients = await notification_service._collect_faction_recipients(1, notification_service.EVENT_BATTLE)

    assert recipients == {}


@pytest.mark.asyncio
async def test_battle_notifies_both_sides_not_bystanders(patched):
    patched["faction_recipient_rows"][1] = [{"faction_id": 1, "user_id": 100, "is_leader": True}]
    patched["faction_recipient_rows"][2] = [{"faction_id": 2, "user_id": 200, "is_leader": True}]
    patched["faction_recipient_rows"][3] = [{"faction_id": 3, "user_id": 300, "is_leader": True}]
    patched["settings"][100] = make_settings(battle=True)
    patched["settings"][200] = make_settings(battle=True)
    patched["settings"][300] = make_settings(battle=True)

    recipients = {}
    for faction_id in (1, 2):
        recipients.update(await notification_service._collect_faction_recipients(faction_id, notification_service.EVENT_BATTLE))

    assert 100 in recipients
    assert 200 in recipients
    assert 300 not in recipients


@pytest.mark.asyncio
async def test_member_with_matching_allegiance_receives_alerts(patched):
    patched["leader_rows"][10] = [
        {"faction_id": 1, "user_id": 100, "is_leader": True, "is_own": False},
        {"faction_id": 1, "user_id": 101, "is_leader": False, "is_own": False},
    ]
    patched["settings"][100] = make_settings(own=False)
    patched["settings"][101] = make_settings(own=False)

    recipients = await notification_service._collect_recipients(10, None, None, notification_service.EVENT_TRANSFER)

    assert 100 in recipients
    assert 101 in recipients


@pytest.mark.asyncio
async def test_member_with_no_allegiance_does_not_receive(patched):
    patched["leader_rows"][10] = [
        {"faction_id": 1, "user_id": 100, "is_leader": True, "is_own": False},
    ]
    patched["settings"][100] = make_settings(own=False)

    recipients = await notification_service._collect_recipients(10, None, None, notification_service.EVENT_TRANSFER)

    assert list(recipients.keys()) == [100]


@pytest.mark.asyncio
async def test_member_of_different_faction_does_not_receive(patched):
    patched["leader_rows"][10] = [
        {"faction_id": 1, "user_id": 100, "is_leader": True, "is_own": False},
    ]
    patched["settings"][100] = make_settings(own=False)
    patched["settings"][999] = make_settings(own=False)

    recipients = await notification_service._collect_recipients(10, None, None, notification_service.EVENT_TRANSFER)

    assert 999 not in recipients


@pytest.mark.asyncio
async def test_leader_still_notified_when_own_allegiance_unset(patched):
    patched["leader_rows"][10] = [
        {"faction_id": 1, "user_id": 100, "is_leader": True, "is_own": True},
    ]
    patched["settings"][100] = make_settings(own=True)

    recipients = await notification_service._collect_recipients(10, None, 1, notification_service.EVENT_TRANSFER)

    assert 100 in recipients


@pytest.mark.asyncio
async def test_leader_with_matching_allegiance_not_duplicated(patched):
    patched["leader_rows"][10] = [
        {"faction_id": 1, "user_id": 100, "is_leader": True, "is_own": True},
    ]
    patched["settings"][100] = make_settings(own=True)

    recipients = await notification_service._collect_recipients(10, None, 1, notification_service.EVENT_TRANSFER)

    assert list(recipients.keys()).count(100) == 1


@pytest.mark.asyncio
async def test_member_respects_own_toggles_and_mode_off(patched):
    patched["leader_rows"][10] = [
        {"faction_id": 1, "user_id": 100, "is_leader": True, "is_own": False},
        {"faction_id": 1, "user_id": 101, "is_leader": False, "is_own": False},
        {"faction_id": 1, "user_id": 102, "is_leader": False, "is_own": False},
    ]
    patched["settings"][100] = make_settings(own=False)
    patched["settings"][101] = make_settings(mode="off", own=False)
    patched["settings"][102] = make_settings(own=False, transfers=False)

    recipients = await notification_service._collect_recipients(10, None, None, notification_service.EVENT_TRANSFER)

    assert 100 in recipients
    assert 101 not in recipients
    assert 102 not in recipients


@pytest.mark.asyncio
async def test_own_only_event_reaches_members_of_acting_faction(patched):
    patched["faction_recipient_rows"][1] = [
        {"faction_id": 1, "user_id": 100, "is_leader": True},
        {"faction_id": 1, "user_id": 101, "is_leader": False},
    ]
    patched["settings"][100] = make_settings(recruitment=True)
    patched["settings"][101] = make_settings(recruitment=True)

    recipients = await notification_service._collect_faction_recipients(1, notification_service.EVENT_RECRUITMENT)

    assert 100 in recipients
    assert 101 in recipients


@pytest.mark.asyncio
async def test_own_only_event_never_reaches_members_of_another_faction(patched):
    patched["faction_recipient_rows"][1] = [
        {"faction_id": 1, "user_id": 100, "is_leader": True},
    ]
    patched["faction_recipient_rows"][2] = [
        {"faction_id": 2, "user_id": 200, "is_leader": True},
        {"faction_id": 2, "user_id": 201, "is_leader": False},
    ]
    patched["settings"][100] = make_settings(recruitment=True)
    patched["settings"][200] = make_settings(recruitment=True)
    patched["settings"][201] = make_settings(recruitment=True)

    recipients = await notification_service._collect_faction_recipients(1, notification_service.EVENT_RECRUITMENT)

    assert 200 not in recipients
    assert 201 not in recipients
