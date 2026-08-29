# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from services.scripting.parser import parse
from services.scripting.type_checker import check as type_check
from services.scripting.executor import execute_script_manual, _deactivate_if_stopped
from services.scripting.errors import FALSyntaxError


def test_stop_parses_and_type_checks():
    script = "IF CM > 500K:\n    STOP\n"
    ast = parse(script)
    tc = type_check(ast)
    assert tc.ok


def test_resource_expr_parses_and_type_checks():
    script = "SET reserve = CM * 50 / 100\nIF CM > reserve:\n    STOP\n"
    ast = parse(script)
    tc = type_check(ast)
    assert tc.ok


async def test_stop_sets_stopped_and_aborted(fake_db):
    fake_db.fetchrow_queue.append({'total': 1000})
    script = "IF CM > 500:\n    STOP\n"
    result = await execute_script_manual(script, faction_id=1, dry_run=False)
    assert result.stopped is True
    assert result.aborted is True
    assert not result.errors


async def test_stop_halts_remaining_statements(fake_db):
    fake_db.fetchrow_queue.append({'total': 1000})
    script = (
        "IF CM > 500:\n"
        "    STOP\n"
        "SET x = 1 + 1\n"
    )
    result = await execute_script_manual(script, faction_id=1, dry_run=False)
    assert result.stopped is True
    fetch_calls = [e for e in fake_db.executed if e[0] == 'fetchrow']
    assert len(fetch_calls) == 1


async def test_stop_not_triggered_when_condition_false(fake_db):
    fake_db.fetchrow_queue.append({'total': 100})
    script = "IF CM > 500:\n    STOP\n"
    result = await execute_script_manual(script, faction_id=1, dry_run=False)
    assert result.stopped is False
    assert result.aborted is False


async def test_dry_run_stop_does_not_deactivate(fake_db):
    from services.scripting.runtime import ExecutionResult

    result = ExecutionResult(dry_run=True)
    result.stopped = True

    deactivated = []

    async def fake_deactivate(script_id, faction_id):
        deactivated.append((script_id, faction_id))

    import services.scripting.script_service as script_service
    orig = script_service.deactivate_script
    script_service.deactivate_script = fake_deactivate
    try:
        await _deactivate_if_stopped(result, script_id=1, faction_id=2)
    finally:
        script_service.deactivate_script = orig

    assert deactivated == []


async def test_live_run_stop_deactivates_script():
    from services.scripting.runtime import ExecutionResult

    result = ExecutionResult(dry_run=False)
    result.stopped = True

    deactivated = []

    async def fake_deactivate(script_id, faction_id):
        deactivated.append((script_id, faction_id))

    import services.scripting.script_service as script_service
    from services.scripting.executor import _deactivate_if_stopped
    orig = script_service.deactivate_script
    script_service.deactivate_script = fake_deactivate
    try:
        await _deactivate_if_stopped(result, script_id=7, faction_id=3)
    finally:
        script_service.deactivate_script = orig

    assert deactivated == [(7, 3)]


async def test_live_run_without_stop_does_not_deactivate():
    from services.scripting.runtime import ExecutionResult

    result = ExecutionResult(dry_run=False)
    result.stopped = False

    deactivated = []

    async def fake_deactivate(script_id, faction_id):
        deactivated.append((script_id, faction_id))

    import services.scripting.script_service as script_service
    from services.scripting.executor import _deactivate_if_stopped
    orig = script_service.deactivate_script
    script_service.deactivate_script = fake_deactivate
    try:
        await _deactivate_if_stopped(result, script_id=7, faction_id=3)
    finally:
        script_service.deactivate_script = orig

    assert deactivated == []


async def test_deactivate_script_is_idempotent(fake_db):
    from repositories import script_repo

    fake_db.executed.clear()
    await script_repo.deactivate_script(script_id=1, faction_id=2)

    update_calls = [e for e in fake_db.executed if e[0] == 'execute']
    assert len(update_calls) == 1
    assert "is_active = TRUE" in update_calls[0][1]
    assert "SET is_active = FALSE" in update_calls[0][1]
