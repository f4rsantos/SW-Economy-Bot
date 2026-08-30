# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import json
from datetime import datetime
from typing import Optional, List
from database.db_manager import db
from dtos.transfer import Transfer, TransferResource, TransferResourceBulk, PendingTransfer


def get_connection():
    return db.get_connection()


async def call_deduct_resources(faction_id: int, world_id: Optional[int], resources_json: str, conn=None):
    executor = conn if conn is not None else db
    await executor.execute(
        "SELECT sp_deduct_resources($1, $2, $3::jsonb)",
        faction_id, world_id, resources_json
    )


async def call_add_resources(faction_id: int, world_id: Optional[int], resources_json: str):
    await db.execute(
        "SELECT sp_add_resources($1, $2, $3::jsonb)",
        faction_id, world_id, resources_json
    )


async def call_upgrade_buildings(faction_id: int, world_id: int, building_id: int, amount: int,
                                 source_level: int, target_level: int, costs_json: str):
    await db.execute(
        "SELECT sp_upgrade_buildings($1, $2, $3, $4, $5, $6, $7::jsonb)",
        faction_id, world_id, building_id, amount, source_level, target_level,
        costs_json
    )


async def get_resource_ids_by_names(resource_names: list) -> List[dict]:
    return await db.fetch(
        "SELECT id, name FROM resources WHERE name = ANY($1)", resource_names
    )


async def call_create_transfer(from_faction_id: int, to_faction_id: int, from_world_id: int, to_world_id: int,
                               resources_json: str, start_time: datetime, arrival_time: datetime,
                               escort_fleet_id: Optional[int]) -> dict:
    return await db.fetchrow(
        "SELECT sp_create_transfer($1, $2, $3, $4, $5::jsonb, $6, $7, $8) as transfer_id",
        from_faction_id, to_faction_id, from_world_id, to_world_id,
        resources_json, start_time, arrival_time, escort_fleet_id
    )


async def call_deposit_transfer(transfer_id: int):
    await db.execute("SELECT sp_deposit_transfer($1)", transfer_id)


async def call_intercept_transfer(transfer_id: int, fleet_id: int, world_id: int):
    await db.execute("SELECT sp_intercept_transfer($1, $2, $3)", transfer_id, fleet_id, world_id)


async def call_seize_transfer(transfer_id: int, faction_id: int, world_id: int):
    await db.execute("SELECT sp_seize_transfer($1, $2, $3)", transfer_id, faction_id, world_id)


async def call_destroy_transfer(transfer_id: int):
    await db.execute("SELECT sp_destroy_transfer($1)", transfer_id)


async def call_release_transfer(transfer_id: int, new_arrival: datetime):
    await db.execute("SELECT sp_release_transfer($1, $2)", transfer_id, new_arrival)


async def get_transfer_row(transfer_id: int, status: str = None) -> Optional[Transfer]:
    condition = "AND ts.name = $2" if status else ""
    params = [transfer_id]
    if status:
        params.append(status)
    row = await db.fetchrow(f"""
        SELECT rt.*, ts.name as status,
               ff.name as from_faction_name,
               tf.name as to_faction_name,
               fw.name as from_world_name,
               tw.name as to_world_name
        FROM resource_transfers rt
        JOIN transfer_statuses ts ON rt.status_id = ts.id
        JOIN factions ff ON rt.from_faction_id = ff.id
        JOIN factions tf ON rt.to_faction_id = tf.id
        JOIN worlds fw ON rt.from_world_id = fw.id
        JOIN worlds tw ON rt.to_world_id = tw.id
        WHERE rt.id = $1 {condition}
    """, *params)
    return Transfer.from_row(row) if row else None


async def get_intercepted_transfer_row(transfer_id: int, intercepting_faction_id: int) -> Optional[Transfer]:
    row = await db.fetchrow("""
        SELECT rt.*, ts.name as status,
               ff.name as from_faction_name,
               tf.name as to_faction_name,
               fw.name as from_world_name,
               tw.name as to_world_name
        FROM resource_transfers rt
        JOIN transfer_statuses ts ON rt.status_id = ts.id
        JOIN factions ff ON rt.from_faction_id = ff.id
        JOIN factions tf ON rt.to_faction_id = tf.id
        JOIN worlds fw ON rt.from_world_id = fw.id
        JOIN worlds tw ON rt.to_world_id = tw.id
        WHERE rt.id = $1 AND ts.name = 'intercepted' AND rt.intercepting_faction_id = $2
    """, transfer_id, intercepting_faction_id)
    return Transfer.from_row(row) if row else None


async def get_transfer_resources_rows(transfer_id: int) -> List[TransferResource]:
    rows = await db.fetch("""
        SELECT tr.resource_id, tr.amount, r.name
        FROM transfer_resources tr
        JOIN resources r ON tr.resource_id = r.id
        WHERE tr.transfer_id = $1
    """, transfer_id)
    return TransferResource.from_rows(rows)


async def get_fleets_at_world_rows(faction_id: int, world_id: int) -> List[dict]:
    return await db.fetch("""
        SELECT f.id, f.name, f.faction_fleet_number, fs.name as status
        FROM fleets f
        JOIN fleet_status fs ON f.status_id = fs.id
        WHERE f.faction_id = $1 AND f.position = $2
        ORDER BY f.faction_fleet_number
    """, faction_id, world_id)


async def get_blockade_row(world_id: int, faction_id: int) -> Optional[dict]:
    return await db.fetchrow("""
        SELECT b.id FROM blockades b
        JOIN blockade_targets bt ON b.id = bt.blockade_id
        WHERE b.world_id = $1 AND bt.faction_id = $2
    """, world_id, faction_id)


async def debit_faction_treasury(from_faction_id: int, er_id: int, amount: int):
    await db.execute(
        "UPDATE faction_treasury SET amount = amount - $1 WHERE faction_id = $2 AND resource_id = $3",
        amount, from_faction_id, er_id
    )


async def credit_faction_treasury(to_faction_id: int, er_id: int, amount: int):
    await db.execute("""
        INSERT INTO faction_treasury (faction_id, resource_id, amount)
        VALUES ($1, $2, $3)
        ON CONFLICT (faction_id, resource_id)
        DO UPDATE SET amount = faction_treasury.amount + $3
    """, to_faction_id, er_id, amount)


async def get_resource_name_to_id_rows(resource_names: list) -> List[dict]:
    return await db.fetch("SELECT id, name FROM resources WHERE name = ANY($1)", resource_names)


async def get_world_for_faction_row(faction_id: int) -> Optional[dict]:
    row = await db.fetchrow(
        """
        SELECT w.id, w.name FROM worlds w
        JOIN world_factions wf ON w.id = wf.world_id
        WHERE wf.faction_id = $1 LIMIT 1
        """,
        faction_id,
    )
    return dict(row) if row else None


async def ensure_world_presence(world_id: int, faction_id: int):
    await db.execute(
        "INSERT INTO world_factions (world_id, faction_id, territory) VALUES ($1, $2, 0) ON CONFLICT DO NOTHING",
        world_id,
        faction_id,
    )


async def get_world_presence_row(world_id: int, faction_id: int) -> Optional[dict]:
    return await db.fetchrow(
        "SELECT faction_id FROM world_factions WHERE world_id = $1 AND faction_id = $2",
        world_id,
        faction_id,
    )


async def get_local_resource_amount_row(world_id: int, faction_id: int, resource_id: int) -> Optional[dict]:
    return await db.fetchrow(
        "SELECT amount FROM local_treasury WHERE world_id = $1 AND faction_id = $2 AND resource_id = $3",
        world_id,
        faction_id,
        resource_id,
    )


async def get_pending_transfers_rows(where_clause: str, params: list) -> List[PendingTransfer]:
    rows = await db.fetch(
        f"""
        SELECT rt.id, ts.name as status, rt.arrival_time,
               COALESCE(ff.formal_name, ff.name) as from_faction_name,
               COALESCE(tf.formal_name, tf.name) as to_faction_name,
               fw.name as from_world_name, tw.name as to_world_name,
               iw.name as interception_world_name,
               COALESCE(if_fac.formal_name, if_fac.name) as intercepting_faction_name,
               CASE WHEN rt.intercepted_by_fleet_id IS NOT NULL
                    THEN COALESCE(inf.name, 'Unit #' || inf.faction_fleet_number)
                    END as intercepting_unit_name,
               CASE WHEN rt.escort_fleet_id IS NOT NULL
                    THEN COALESCE(ef.name, 'Unit #' || ef.faction_fleet_number)
                    END as escort_name
        FROM resource_transfers rt
        JOIN transfer_statuses ts ON rt.status_id = ts.id
        JOIN factions ff ON rt.from_faction_id = ff.id
        JOIN factions tf ON rt.to_faction_id = tf.id
        JOIN worlds fw ON rt.from_world_id = fw.id
        JOIN worlds tw ON rt.to_world_id = tw.id
        LEFT JOIN worlds iw ON rt.interception_world_id = iw.id
        LEFT JOIN factions if_fac ON rt.intercepting_faction_id = if_fac.id
        LEFT JOIN fleets inf ON rt.intercepted_by_fleet_id = inf.id
        LEFT JOIN fleets ef ON rt.escort_fleet_id = ef.id
        WHERE {where_clause} AND ts.name IN ('in_transit', 'intercepted')
        ORDER BY rt.arrival_time ASC
        """,
        *params,
    )
    return PendingTransfer.from_rows(rows)


async def get_transfer_resource_rows_bulk(transfer_ids: list) -> List[TransferResourceBulk]:
    rows = await db.fetch(
        """
        SELECT tr.transfer_id, tr.amount, r.name
        FROM transfer_resources tr
        JOIN resources r ON tr.resource_id = r.id
        WHERE tr.transfer_id = ANY($1)
        """,
        transfer_ids,
    )
    return TransferResourceBulk.from_rows(rows)
