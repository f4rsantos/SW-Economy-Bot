# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import math
import pytest

from services import megaproject_service
from repositories import megaproject_repo


def test_terraformer_cost_scales_per_hex():
    costs = megaproject_service.calculate_terraformer_cost(100)
    assert costs['CM'] == 20_000 * 100
    assert costs['EL'] == 20_000 * 100
    assert costs['CS'] == 30_000 * 100


def test_terraformer_alloy_cost_rounds_up_per_50_hexes():
    costs_50 = megaproject_service.calculate_terraformer_cost(50)
    costs_51 = megaproject_service.calculate_terraformer_cost(51)
    costs_100 = megaproject_service.calculate_terraformer_cost(100)
    costs_101 = megaproject_service.calculate_terraformer_cost(101)

    assert costs_50['Alloys'] == 100 + 1
    assert costs_51['Alloys'] == 100 + 2
    assert costs_100['Alloys'] == 100 + 2
    assert costs_101['Alloys'] == 100 + 3


def test_terraformer_alloy_cost_small_world_rounds_up_to_one_block():
    costs = megaproject_service.calculate_terraformer_cost(1)
    assert costs['Alloys'] == 100 + 1


def test_terraformer_maintenance_scales_per_hex():
    maintenance = megaproject_service.calculate_terraformer_maintenance(40)
    assert maintenance['CM'] == 100 * 40
    assert maintenance['EL'] == 100 * 40


def test_recycling_center_flat_cost():
    costs = megaproject_service.calculate_recycling_center_cost()
    assert costs['CM'] == 10_000_000
    assert costs['EL'] == 10_000_000
    assert costs['CS'] == 20_000_000
    assert costs['Alloys'] == 20


def test_extractors_upgrade_flat_cost():
    costs = megaproject_service.calculate_extractors_upgrade_cost()
    assert costs['CM'] == 10_000_000
    assert costs['EL'] == 10_000_000
    assert costs['CS'] == 20_000_000
    assert costs['Alloys'] == 20


def test_recycling_refund_is_five_percent_of_refined_spend():
    refund = megaproject_service.calculate_recycling_refund({'CM': 1000, 'EL': 2000, 'CS': 300})
    assert refund['CM'] == 50
    assert refund['EL'] == 100
    assert refund['CS'] == 15


def test_recycling_refund_ignores_negative_net_spend():
    refund = megaproject_service.calculate_recycling_refund({'CM': -500, 'EL': 0})
    assert refund == {}


def test_recycling_refund_floors_fractional_amounts():
    refund = megaproject_service.calculate_recycling_refund({'CM': 19})
    assert refund.get('CM', 0) == 0
    assert 'CM' not in refund


async def test_build_terraformer_rejects_when_world_already_has_one(monkeypatch):
    project_type = megaproject_repo.MegaprojectType(
        id=1, code='terraformer', name='Terraformer', description=None,
        is_world_scoped=True, one_per_world=True, one_per_faction=False, has_maintenance=True,
    )

    async def fake_get_type_by_code(code):
        return project_type

    async def fake_get_faction_project_by_type(faction_id, type_id, world_id=None):
        return {'id': 1}

    monkeypatch.setattr(megaproject_repo, "get_type_by_code", fake_get_type_by_code)
    monkeypatch.setattr(megaproject_repo, "get_faction_project_by_type", fake_get_faction_project_by_type)

    with pytest.raises(ValueError, match="already been built"):
        await megaproject_service.build_terraformer(faction_id=10, world_id=5, world_name="Corellia")


async def test_build_recycling_center_rejects_second_instance(monkeypatch):
    project_type = megaproject_repo.MegaprojectType(
        id=2, code='recycling_center', name='Resource Recycling Center', description=None,
        is_world_scoped=False, one_per_world=False, one_per_faction=True, has_maintenance=True,
    )

    async def fake_get_type_by_code(code):
        return project_type

    async def fake_get_faction_project_by_type(faction_id, type_id, world_id=None):
        return {'id': 7}

    monkeypatch.setattr(megaproject_repo, "get_type_by_code", fake_get_type_by_code)
    monkeypatch.setattr(megaproject_repo, "get_faction_project_by_type", fake_get_faction_project_by_type)

    with pytest.raises(ValueError, match="already has a Resource Recycling Center"):
        await megaproject_service.build_recycling_center(faction_id=10)


async def test_build_extractors_upgrade_rejects_second_instance(monkeypatch):
    project_type = megaproject_repo.MegaprojectType(
        id=3, code='extractors_upgrade', name='Extractors Upgrade', description=None,
        is_world_scoped=False, one_per_world=False, one_per_faction=True, has_maintenance=False,
    )

    async def fake_get_type_by_code(code):
        return project_type

    async def fake_get_faction_project_by_type(faction_id, type_id, world_id=None):
        return {'id': 9}

    monkeypatch.setattr(megaproject_repo, "get_type_by_code", fake_get_type_by_code)
    monkeypatch.setattr(megaproject_repo, "get_faction_project_by_type", fake_get_faction_project_by_type)

    with pytest.raises(ValueError, match="already has the Extractors Upgrade"):
        await megaproject_service.build_extractors_upgrade(faction_id=10)


class _FakeConn:
    def __init__(self, insufficient=False):
        self.insufficient = insufficient

    def transaction(self):
        return _FakeTxCtx()


class _FakeTxCtx:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeConnCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


async def test_build_terraformer_insufficient_resources_is_rejected(monkeypatch):
    project_type = megaproject_repo.MegaprojectType(
        id=1, code='terraformer', name='Terraformer', description=None,
        is_world_scoped=True, one_per_world=True, one_per_faction=False, has_maintenance=True,
    )

    async def fake_get_type_by_code(code):
        return project_type

    async def fake_get_faction_project_by_type(faction_id, type_id, world_id=None):
        return None

    async def fake_get_active_projects_by_type_code(code):
        return []

    async def fake_get_world_hex_count(world_id):
        return 10

    def fake_get_connection():
        return _FakeConnCtx(_FakeConn())

    async def fake_deduct_resources(faction_id, world_id, resources, conn=None):
        raise ValueError("RESOURCE_INSUFFICIENT: Insufficient CM")

    monkeypatch.setattr(megaproject_repo, "get_type_by_code", fake_get_type_by_code)
    monkeypatch.setattr(megaproject_repo, "get_faction_project_by_type", fake_get_faction_project_by_type)
    monkeypatch.setattr(megaproject_repo, "get_active_projects_by_type_code", fake_get_active_projects_by_type_code)
    monkeypatch.setattr(megaproject_repo, "get_world_hex_count", fake_get_world_hex_count)
    monkeypatch.setattr(megaproject_repo, "get_connection", fake_get_connection)
    monkeypatch.setattr(megaproject_service, "deduct_resources", fake_deduct_resources)

    with pytest.raises(ValueError, match="RESOURCE_INSUFFICIENT"):
        await megaproject_service.build_terraformer(faction_id=10, world_id=5, world_name="Corellia")


async def test_charge_or_disable_charges_when_resources_available(monkeypatch):
    charged = []

    async def fake_deduct_resources(faction_id, world_id, resources, conn=None):
        charged.append((faction_id, world_id, resources))

    monkeypatch.setattr(megaproject_service, "deduct_resources", fake_deduct_resources)

    result = await megaproject_service._charge_or_disable(10, None, 1, {'CM': 100}, deduct_world_id=None)

    assert result['charged'] is True
    assert result['disabled'] is False
    assert charged == [(10, None, {'CM': 100})]


async def test_charge_or_disable_disables_project_when_payment_fails(monkeypatch):
    async def fake_deduct_resources(faction_id, world_id, resources, conn=None):
        raise ValueError("RESOURCE_INSUFFICIENT: Insufficient CM")

    disabled_ids = []

    async def fake_set_active(project_id, is_active):
        disabled_ids.append((project_id, is_active))
        return "UPDATE 1"

    monkeypatch.setattr(megaproject_service, "deduct_resources", fake_deduct_resources)
    monkeypatch.setattr(megaproject_repo, "set_active", fake_set_active)

    result = await megaproject_service._charge_or_disable(10, None, 1, {'CM': 100}, deduct_world_id=None)

    assert result['charged'] is False
    assert result['disabled'] is True
    assert disabled_ids == [(1, False)]


async def test_charge_or_disable_disabling_is_idempotent(monkeypatch):
    async def fake_deduct_resources(faction_id, world_id, resources, conn=None):
        raise ValueError("RESOURCE_INSUFFICIENT: Insufficient CM")

    async def fake_set_active(project_id, is_active):
        return "UPDATE 0"

    monkeypatch.setattr(megaproject_service, "deduct_resources", fake_deduct_resources)
    monkeypatch.setattr(megaproject_repo, "set_active", fake_set_active)

    result = await megaproject_service._charge_or_disable(10, None, 1, {'CM': 100}, deduct_world_id=None)

    assert result['charged'] is False
    assert result['disabled'] is False


async def test_reactivate_project_rejects_when_already_active(monkeypatch):
    project = megaproject_repo.FactionMegaproject(
        id=1, faction_id=10, megaproject_type_id=2, type_code='recycling_center',
        type_name='Resource Recycling Center', world_id=None, world_name=None,
        is_active=True, built_at=None, disabled_at=None,
    )

    async def fake_get_project_detail(faction_id, project_id):
        return project

    monkeypatch.setattr(megaproject_repo, "get_project_detail", fake_get_project_detail)

    with pytest.raises(ValueError, match="already active"):
        await megaproject_service.reactivate_project(10, 1)


async def test_reactivate_project_charges_terraformer_maintenance(monkeypatch):
    project = megaproject_repo.FactionMegaproject(
        id=1, faction_id=10, megaproject_type_id=1, type_code='terraformer',
        type_name='Terraformer', world_id=5, world_name='Corellia',
        is_active=False, built_at=None, disabled_at=None,
    )

    async def fake_get_project_detail(faction_id, project_id):
        return project

    async def fake_get_world_hex_count(world_id):
        return 20

    charged = []

    async def fake_deduct_resources(faction_id, world_id, resources, conn=None):
        charged.append((faction_id, world_id, resources))

    async def fake_set_active(project_id, is_active):
        return "UPDATE 1"

    monkeypatch.setattr(megaproject_repo, "get_project_detail", fake_get_project_detail)
    monkeypatch.setattr(megaproject_repo, "get_world_hex_count", fake_get_world_hex_count)
    monkeypatch.setattr(megaproject_service, "deduct_resources", fake_deduct_resources)
    monkeypatch.setattr(megaproject_repo, "set_active", fake_set_active)

    result = await megaproject_service.reactivate_project(10, 1)

    assert result['costs'] == {'CM': 100 * 20, 'EL': 100 * 20}
    assert charged == [(10, 5, {'CM': 2000, 'EL': 2000})]


def test_extractor_self_refine_production_scale():
    ratio = megaproject_service.EXTRACTOR_SELF_REFINE_PRODUCTION / megaproject_service.EXTRACTOR_BASE_PRODUCTION
    assert ratio == pytest.approx(0.7)


def test_compute_world_production_self_refining_bypasses_refinery_capacity():
    from services.income_calculator import compute_world_production

    unrefined_data_map = {
        1: {'U-CM': {'base_production': 1000, 'percentage': 100}}
    }
    refined_capacity_map = {1: {'CM': 0}}
    stock_map = {}
    refined_stock_map = {}
    storage_capacity_map = {1: {'CM': 10_000}}
    outgoing_trade_map = {}
    efficiency_cache = {('extractor', 'CM'): 1.0, ('refinery', 'CM'): 1.0}

    world_resources, unrefined_prod, refined, unrefined_consumed = compute_world_production(
        1, unrefined_data_map, refined_capacity_map, stock_map, refined_stock_map,
        storage_capacity_map, outgoing_trade_map, efficiency_cache,
        self_refining=True, self_refine_production_scale=0.7,
    )

    assert refined['CM'] == 700
    assert unrefined_prod['U-CM'] == 0


def test_compute_world_production_self_refining_respects_storage_cap():
    from services.income_calculator import compute_world_production

    unrefined_data_map = {
        1: {'U-CM': {'base_production': 1000, 'percentage': 100}}
    }
    refined_capacity_map = {1: {'CM': 0}}
    stock_map = {}
    refined_stock_map = {1: {'CM': 650}}
    storage_capacity_map = {1: {'CM': 700}}
    outgoing_trade_map = {}
    efficiency_cache = {('extractor', 'CM'): 1.0, ('refinery', 'CM'): 1.0}

    world_resources, unrefined_prod, refined, unrefined_consumed = compute_world_production(
        1, unrefined_data_map, refined_capacity_map, stock_map, refined_stock_map,
        storage_capacity_map, outgoing_trade_map, efficiency_cache,
        self_refining=True, self_refine_production_scale=0.7,
    )

    assert refined['CM'] == 50


def test_compute_world_production_without_self_refining_uses_full_production_and_refinery():
    from services.income_calculator import compute_world_production

    unrefined_data_map = {
        1: {'U-CM': {'base_production': 1000, 'percentage': 100}}
    }
    refined_capacity_map = {1: {'CM': 500}}
    stock_map = {}
    refined_stock_map = {}
    storage_capacity_map = {1: {'CM': 10_000}}
    outgoing_trade_map = {}
    efficiency_cache = {('extractor', 'CM'): 1.0, ('refinery', 'CM'): 1.0}

    world_resources, unrefined_prod, refined, unrefined_consumed = compute_world_production(
        1, unrefined_data_map, refined_capacity_map, stock_map, refined_stock_map,
        storage_capacity_map, outgoing_trade_map, efficiency_cache,
    )

    assert unrefined_prod['U-CM'] == 1000
    assert refined['CM'] == 500
    assert world_resources['U-CM'] == 500


async def test_get_megaproject_efficiency_penalty_applies_when_active(monkeypatch):
    from services import building_efficiency_service

    async def fake_has_active_recycling_center(faction_id):
        return True

    monkeypatch.setattr(megaproject_service, "has_active_recycling_center", fake_has_active_recycling_center)

    penalty = await building_efficiency_service.get_megaproject_efficiency_penalty(10)
    assert penalty == megaproject_service.RECYCLING_CENTER_EFFICIENCY_PENALTY


async def test_get_megaproject_efficiency_penalty_zero_when_inactive(monkeypatch):
    from services import building_efficiency_service

    async def fake_has_active_recycling_center(faction_id):
        return False

    monkeypatch.setattr(megaproject_service, "has_active_recycling_center", fake_has_active_recycling_center)

    penalty = await building_efficiency_service.get_megaproject_efficiency_penalty(10)
    assert penalty == 0.0


async def test_reset_snapshot_and_report_populates_last_cycle_table(monkeypatch):
    from database.db_manager import db

    class _SnapshotConn:
        def __init__(self):
            self.executed = []
            self.executemany_calls = []

        def transaction(self):
            return _FakeTxCtx()

        async def fetch(self, query, *args):
            self.executed.append((query, args))
            if "DELETE FROM faction_weekly_spend" in query:
                return [{'faction_id': 10, 'resource_id': 1, 'amount': 500, 'direction': 1}]
            if "SELECT r.name AS resource_name" in query:
                return [{'resource_name': 'CM', 'amount': 500}]
            return []

        async def execute(self, query, *args):
            self.executed.append((query, args))
            return "OK"

        async def executemany(self, query, args_list):
            self.executemany_calls.append((query, args_list))
            return "OK"

    conn = _SnapshotConn()
    monkeypatch.setattr(db, "get_connection", lambda: _FakeConnCtx(conn))

    from services import spend_service

    async def on_reset(totals):
        return True

    totals = await spend_service.reset_snapshot_and_report(on_reset)

    assert totals[0].resource_name == 'CM'
    assert totals[0].amount == 500
    assert len(conn.executemany_calls) == 1
    inserted_query, inserted_rows = conn.executemany_calls[0]
    assert "faction_last_cycle_spend" in inserted_query


def _recycling_center_type():
    return megaproject_repo.MegaprojectType(
        id=2, code='recycling_center', name='Resource Recycling Center', description=None,
        is_world_scoped=False, one_per_world=False, one_per_faction=True, has_maintenance=True,
    )


async def test_contribute_partial_accumulates(monkeypatch):
    project_type = _recycling_center_type()

    async def fake_get_type_by_code(code):
        return project_type

    async def fake_get_faction_project_by_type(faction_id, type_id, world_id=None):
        return None

    async def fake_get_megaproject_progress_rows(faction_id, type_id, world_id):
        return []

    upserted = []

    async def fake_upsert_megaproject_progress_resource(conn, faction_id, type_id, world_id, resource_name, amount):
        upserted.append((resource_name, amount))
        return amount

    deducted = []

    async def fake_deduct_resources(faction_id, world_id, resources, conn=None):
        deducted.append(resources)

    def fake_get_connection():
        return _FakeConnCtx(_FakeConn())

    monkeypatch.setattr(megaproject_repo, "get_type_by_code", fake_get_type_by_code)
    monkeypatch.setattr(megaproject_repo, "get_faction_project_by_type", fake_get_faction_project_by_type)
    monkeypatch.setattr(megaproject_repo, "get_megaproject_progress_rows", fake_get_megaproject_progress_rows)
    monkeypatch.setattr(megaproject_repo, "upsert_megaproject_progress_resource", fake_upsert_megaproject_progress_resource)
    monkeypatch.setattr(megaproject_repo, "get_connection", fake_get_connection)
    monkeypatch.setattr(megaproject_service, "deduct_resources", fake_deduct_resources)

    result = await megaproject_service.contribute_to_megaproject(
        faction_id=10, type_code=megaproject_service.RECYCLING_CENTER, world_id=None,
        resources={'CM': 1_000_000},
    )

    assert result['completed'] is False
    assert result['contributed'] == {'CM': 1_000_000}
    assert result['progress']['CM'] == 1_000_000
    assert deducted == [{'CM': 1_000_000}]
    assert upserted == [('CM', 1_000_000)]


async def test_contribute_overpay_is_clamped_to_target(monkeypatch):
    project_type = _recycling_center_type()

    async def fake_get_type_by_code(code):
        return project_type

    async def fake_get_faction_project_by_type(faction_id, type_id, world_id=None):
        return None

    async def fake_get_megaproject_progress_rows(faction_id, type_id, world_id):
        return []

    async def fake_upsert_megaproject_progress_resource(conn, faction_id, type_id, world_id, resource_name, amount):
        return amount

    deducted = []

    async def fake_deduct_resources(faction_id, world_id, resources, conn=None):
        deducted.append(resources)

    async def fake_insert_project(conn, faction_id, type_id, world_id):
        return 99

    deleted = []

    async def fake_delete_megaproject_progress(conn, faction_id, type_id, world_id):
        deleted.append((faction_id, type_id, world_id))

    def fake_get_connection():
        return _FakeConnCtx(_FakeConn())

    monkeypatch.setattr(megaproject_repo, "get_type_by_code", fake_get_type_by_code)
    monkeypatch.setattr(megaproject_repo, "get_faction_project_by_type", fake_get_faction_project_by_type)
    monkeypatch.setattr(megaproject_repo, "get_megaproject_progress_rows", fake_get_megaproject_progress_rows)
    monkeypatch.setattr(megaproject_repo, "upsert_megaproject_progress_resource", fake_upsert_megaproject_progress_resource)
    monkeypatch.setattr(megaproject_repo, "insert_project", fake_insert_project)
    monkeypatch.setattr(megaproject_repo, "delete_megaproject_progress", fake_delete_megaproject_progress)
    monkeypatch.setattr(megaproject_repo, "get_connection", fake_get_connection)
    monkeypatch.setattr(megaproject_service, "deduct_resources", fake_deduct_resources)

    costs = megaproject_service.calculate_recycling_center_cost()
    overpay = {res: amount * 10 for res, amount in costs.items()}

    result = await megaproject_service.contribute_to_megaproject(
        faction_id=10, type_code=megaproject_service.RECYCLING_CENTER, world_id=None,
        resources=overpay,
    )

    assert result['contributed'] == costs
    assert deducted == [costs]
    assert result['completed'] is True
    assert result['project_id'] == 99
    assert deleted == [(10, project_type.id, None)]


async def test_contribute_completion_inserts_project_and_clears_progress(monkeypatch):
    project_type = _recycling_center_type()
    costs = megaproject_service.calculate_recycling_center_cost()

    async def fake_get_type_by_code(code):
        return project_type

    async def fake_get_faction_project_by_type(faction_id, type_id, world_id=None):
        return None

    async def fake_get_megaproject_progress_rows(faction_id, type_id, world_id):
        return [
            megaproject_repo.MegaprojectProgressRow(resource_name=res, current_amount=amount - 1)
            for res, amount in costs.items()
        ]

    async def fake_upsert_megaproject_progress_resource(conn, faction_id, type_id, world_id, resource_name, amount):
        return costs[resource_name]

    async def fake_deduct_resources(faction_id, world_id, resources, conn=None):
        pass

    inserted = []

    async def fake_insert_project(conn, faction_id, type_id, world_id):
        inserted.append((faction_id, type_id, world_id))
        return 42

    deleted = []

    async def fake_delete_megaproject_progress(conn, faction_id, type_id, world_id):
        deleted.append((faction_id, type_id, world_id))

    def fake_get_connection():
        return _FakeConnCtx(_FakeConn())

    monkeypatch.setattr(megaproject_repo, "get_type_by_code", fake_get_type_by_code)
    monkeypatch.setattr(megaproject_repo, "get_faction_project_by_type", fake_get_faction_project_by_type)
    monkeypatch.setattr(megaproject_repo, "get_megaproject_progress_rows", fake_get_megaproject_progress_rows)
    monkeypatch.setattr(megaproject_repo, "upsert_megaproject_progress_resource", fake_upsert_megaproject_progress_resource)
    monkeypatch.setattr(megaproject_repo, "insert_project", fake_insert_project)
    monkeypatch.setattr(megaproject_repo, "delete_megaproject_progress", fake_delete_megaproject_progress)
    monkeypatch.setattr(megaproject_repo, "get_connection", fake_get_connection)
    monkeypatch.setattr(megaproject_service, "deduct_resources", fake_deduct_resources)

    result = await megaproject_service.contribute_to_megaproject(
        faction_id=10, type_code=megaproject_service.RECYCLING_CENTER, world_id=None,
        resources={res: 1 for res in costs},
    )

    assert result['completed'] is True
    assert result['project_id'] == 42
    assert inserted == [(10, project_type.id, None)]
    assert deleted == [(10, project_type.id, None)]


async def test_contribute_to_already_built_project_raises(monkeypatch):
    project_type = _recycling_center_type()

    async def fake_get_type_by_code(code):
        return project_type

    async def fake_get_faction_project_by_type(faction_id, type_id, world_id=None):
        return {'id': 7}

    monkeypatch.setattr(megaproject_repo, "get_type_by_code", fake_get_type_by_code)
    monkeypatch.setattr(megaproject_repo, "get_faction_project_by_type", fake_get_faction_project_by_type)

    with pytest.raises(ValueError, match="already been built"):
        await megaproject_service.contribute_to_megaproject(
            faction_id=10, type_code=megaproject_service.RECYCLING_CENTER, world_id=None,
            resources={'CM': 100},
        )


async def test_get_megaproject_progress_reports_targets_and_completion(monkeypatch):
    project_type = _recycling_center_type()
    costs = megaproject_service.calculate_recycling_center_cost()

    async def fake_get_type_by_code(code):
        return project_type

    async def fake_get_megaproject_progress_rows(faction_id, type_id, world_id):
        return [megaproject_repo.MegaprojectProgressRow(resource_name='CM', current_amount=costs['CM'])]

    monkeypatch.setattr(megaproject_repo, "get_type_by_code", fake_get_type_by_code)
    monkeypatch.setattr(megaproject_repo, "get_megaproject_progress_rows", fake_get_megaproject_progress_rows)

    result = await megaproject_service.get_megaproject_progress(
        faction_id=10, type_code=megaproject_service.RECYCLING_CENTER, world_id=None,
    )

    assert result['progress']['CM'] == costs['CM']
    assert result['progress']['EL'] == 0
    assert result['completed'] is False
