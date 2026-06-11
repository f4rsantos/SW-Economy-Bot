import asyncio
import json
from typing import Dict, Optional
from database.db_manager import db
from utils.vehicle_utils import get_next_vehicle_number

_vehicle_def_cache: dict[int, dict] = {}


def _parse_vehicle_length(vehicle_data) -> float:
    if not vehicle_data:
        return 100.0
    try:
        for entry in vehicle_data:
            parsed = json.loads(entry) if isinstance(entry, str) else entry
            if parsed and 'length' in parsed:
                return float(parsed['length'])
    except Exception:
        pass
    return 100.0


async def get_vehicle_definition(vehicle_id: int) -> Optional[dict]:
    if vehicle_id in _vehicle_def_cache:
        return _vehicle_def_cache[vehicle_id]
    row, costs = await asyncio.gather(
        db.fetchrow(
            "SELECT v.*, vt.name as type_name FROM vehicles v LEFT JOIN vehicle_types vt ON v.type = vt.id WHERE v.id = $1",
            vehicle_id
        ),
        db.fetch(
            "SELECT r.name, vc.amount FROM vehicle_costs vc JOIN resources r ON vc.resource_id = r.id WHERE vc.vehicle_id = $1",
            vehicle_id
        ),
    )
    if not row:
        return None
    defn = {
        'id': vehicle_id,
        'name': row['name'],
        'designation': row.get('designation'),
        'faction_id': row['faction_id'],
        'faction_vehicle_number': row.get('faction_vehicle_number'),
        'type': row.get('type'),
        'type_name': row.get('type_name'),
        'vehicle_data': row.get('vehicle_data'),
        'length': _parse_vehicle_length(row.get('vehicle_data')),
        'costs': {c['name']: c['amount'] for c in costs},
    }
    _vehicle_def_cache[vehicle_id] = defn
    return defn


def invalidate_vehicle_definition(vehicle_id: int):
    _vehicle_def_cache.pop(vehicle_id, None)


async def get_vehicle_type_id(type_name: str) -> Optional[int]:
    from database.static_cache import static_cache
    type_id = static_cache.get_vehicle_type_id(type_name)
    if type_id is not None:
        return type_id
    result = await db.fetchrow("SELECT id FROM vehicle_types WHERE LOWER(name) = LOWER($1)", type_name)
    return result['id'] if result else None


async def check_vehicle_exists(faction_id: int, vehicle_name: str) -> Optional[Dict]:
    query = """
        SELECT id, name, designation, type
        FROM vehicles
        WHERE faction_id = $1 AND LOWER(name) = LOWER($2)
    """
    result = await db.fetchrow(query, faction_id, vehicle_name)
    return dict(result) if result else None


async def register_vehicle(
    faction_id: int,
    vehicle_name: str,
    designation: Optional[str],
    type_name: str,
    costs: Dict[str, int],
    vehicle_data: Optional[Dict] = None
) -> Dict:
    type_id = await get_vehicle_type_id(type_name)
    if type_id is None:
        raise ValueError(f"Invalid vehicle type: {type_name}")

    next_number = await get_next_vehicle_number(faction_id)

    import json
    vehicle_data_array = [json.dumps(vehicle_data)] if vehicle_data else None

    query = """
        INSERT INTO vehicles (faction_id, type, name, designation, faction_vehicle_number, vehicle_data)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, faction_id, type, name, designation, faction_vehicle_number
    """
    vehicle = await db.fetchrow(query, faction_id, type_id, vehicle_name, designation, next_number, vehicle_data_array)

    from database.static_cache import static_cache
    for resource_name, amount in costs.items():
        if amount > 0:
            res_id = static_cache.get_resource_id(resource_name)
            if res_id:
                await db.execute(
                    "INSERT INTO vehicle_costs (vehicle_id, resource_id, amount) VALUES ($1, $2, $3)",
                    vehicle['id'], res_id, amount
                )

    return dict(vehicle)


async def update_vehicle(
    vehicle_id: int,
    designation: Optional[str],
    costs: Dict[str, int],
    vehicle_data: Optional[Dict] = None
) -> Dict:
    import json
    vehicle_data_array = [json.dumps(vehicle_data)] if vehicle_data else None

    query = """
        UPDATE vehicles
        SET designation = $1, vehicle_data = $2
        WHERE id = $3
        RETURNING id, faction_id, type, name, designation
    """
    vehicle = await db.fetchrow(query, designation, vehicle_data_array, vehicle_id)

    await db.execute("DELETE FROM vehicle_costs WHERE vehicle_id = $1", vehicle_id)
    invalidate_vehicle_definition(vehicle_id)

    from database.static_cache import static_cache
    for resource_name, amount in costs.items():
        if amount > 0:
            res_id = static_cache.get_resource_id(resource_name)
            if res_id:
                await db.execute(
                    "INSERT INTO vehicle_costs (vehicle_id, resource_id, amount) VALUES ($1, $2, $3)",
                    vehicle_id, res_id, amount
                )

    asyncio.create_task(_recalc_cs_for_vehicle(vehicle_id))
    return dict(vehicle)


async def _recalc_cs_for_vehicle(vehicle_id: int):
    await db.execute("""
        UPDATE fleets
        SET total_cs = (
            SELECT COALESCE(SUM(fv.amount * vc.amount), 0)
            FROM fleet_vehicles fv
            JOIN vehicle_costs vc ON fv.vehicle_id = vc.vehicle_id
            JOIN resources r ON vc.resource_id = r.id AND r.name = 'CS'
            WHERE fv.fleet_id = fleets.id
        )
        WHERE id IN (
            SELECT DISTINCT fleet_id FROM fleet_vehicles WHERE vehicle_id = $1
        )
    """, vehicle_id)


async def get_vehicle_costs(vehicle_id: int) -> Dict[str, int]:
    query = """
        SELECT r.name, vc.amount
        FROM vehicle_costs vc
        JOIN resources r ON vc.resource_id = r.id
        WHERE vc.vehicle_id = $1
    """
    results = await db.fetch(query, vehicle_id)
    return {row['name']: row['amount'] for row in results}


async def list_vehicles(faction_id: int) -> list:
    rows = await db.fetch("""
        SELECT v.id, v.name, v.designation, v.faction_vehicle_number,
               vt.name as type_name, v.vehicle_data,
               COALESCE(
                   json_agg(json_build_object('resource', r.name, 'amount', vc.amount) ORDER BY r.name)
                   FILTER (WHERE vc.vehicle_id IS NOT NULL), '[]'
               ) as costs
        FROM vehicles v
        LEFT JOIN vehicle_types vt ON v.type = vt.id
        LEFT JOIN vehicle_costs vc ON v.id = vc.vehicle_id
        LEFT JOIN resources r ON vc.resource_id = r.id
        WHERE v.faction_id = $1
        GROUP BY v.id, v.name, v.designation, v.faction_vehicle_number, vt.name, v.vehicle_data
        ORDER BY v.id
    """, faction_id)
    return [dict(r) for r in rows]


async def rename_vehicle(vehicle_id: int, faction_id: int, new_name: Optional[str], designation: Optional[str]) -> dict:
    if new_name:
        existing = await db.fetchrow(
            "SELECT id FROM vehicles WHERE faction_id = $1 AND LOWER(name) = LOWER($2) AND id != $3",
            faction_id, new_name, vehicle_id
        )
        if existing:
            raise ValueError("A vehicle with that name already exists for this faction.")
    await db.execute(
        "UPDATE vehicles SET name = COALESCE($1, name), designation = COALESCE($2, designation) WHERE id = $3",
        new_name, designation, vehicle_id
    )
    invalidate_vehicle_definition(vehicle_id)


async def set_vehicle_type(vehicle_id: int, type_id: int):
    await db.execute("UPDATE vehicles SET type = $1 WHERE id = $2", type_id, vehicle_id)
    invalidate_vehicle_definition(vehicle_id)


async def deregister_vehicle(vehicle_id: int):
    fleet_check = await db.fetchrow("SELECT SUM(amount) as total FROM fleet_vehicles WHERE vehicle_id = $1", vehicle_id)
    if fleet_check and fleet_check['total'] and fleet_check['total'] > 0:
        raise ValueError(f"Cannot deregister vehicle. {fleet_check['total']} units still exist in fleets.")
    construction_check = await db.fetchrow(
        "SELECT SUM(quantity) as total FROM vehicle_construction WHERE vehicle_id = $1 AND completion_date > CURRENT_TIMESTAMP", vehicle_id
    )
    if construction_check and construction_check['total'] and construction_check['total'] > 0:
        raise ValueError(f"Cannot deregister vehicle. {construction_check['total']} units under construction.")
    await db.execute("DELETE FROM vehicles WHERE id = $1", vehicle_id)
    invalidate_vehicle_definition(vehicle_id)


async def get_vehicle_details(vehicle_id: int) -> tuple[dict, list, list]:
    full_vehicle = await db.fetchrow(
        "SELECT v.*, vt.name as type_name FROM vehicles v LEFT JOIN vehicle_types vt ON v.type = vt.id WHERE v.id = $1",
        vehicle_id
    )
    costs = await db.fetch(
        "SELECT r.name, vc.amount FROM vehicle_costs vc JOIN resources r ON vc.resource_id = r.id WHERE vc.vehicle_id = $1",
        vehicle_id
    )
    fleets_with_vehicle = await db.fetch(
        "SELECT f.faction_fleet_number, f.name as fleet_name, fv.amount FROM fleet_vehicles fv JOIN fleets f ON fv.fleet_id = f.id WHERE fv.vehicle_id = $1 ORDER BY f.faction_fleet_number",
        vehicle_id
    )
    return dict(full_vehicle), [dict(c) for c in costs], [dict(f) for f in fleets_with_vehicle]
