from database.db_manager import db


async def get_fleet_by_id_or_name(identifier: str, faction_id: int = None) -> dict:
    try:
        fleet_number = int(identifier)
        if not faction_id:
            return None
        query = """
            SELECT f.id, f.name, f.faction_id, f.status_id, f.position, f.health, f.total_cs,
                   f.faction_fleet_number,
                   fs.name as status_name, w.name as world_name
            FROM fleets f
            JOIN fleet_status fs ON f.status_id = fs.id
            JOIN worlds w ON f.position = w.id
            WHERE f.faction_fleet_number = $1 AND f.faction_id = $2
        """
        return await db.fetchrow(query, fleet_number, faction_id)
    except ValueError:
        query = """
            SELECT f.id, f.name, f.faction_id, f.status_id, f.position, f.health, f.total_cs,
                   f.faction_fleet_number,
                   fs.name as status_name, w.name as world_name
            FROM fleets f
            JOIN fleet_status fs ON f.status_id = fs.id
            JOIN worlds w ON f.position = w.id
            WHERE LOWER(f.name) = LOWER($1)
        """
        params = [identifier]
        if faction_id:
            query += " AND f.faction_id = $2"
            params.append(faction_id)
        return await db.fetchrow(query, *params)


async def get_vehicle_in_fleet(identifier: str, fleet_id: int, faction_id: int = None) -> dict:
    try:
        vehicle_number = int(identifier)
        query = """
            SELECT v.id, v.name, v.designation, v.faction_id, v.faction_vehicle_number, v.type,
                   vt.name as type_name
            FROM fleet_vehicles fv
            JOIN vehicles v ON fv.vehicle_id = v.id
            LEFT JOIN vehicle_types vt ON v.type = vt.id
            WHERE fv.fleet_id = $1 AND v.faction_vehicle_number = $2
        """
        params = [fleet_id, vehicle_number]
        if faction_id is not None:
            query += " AND v.faction_id = $3"
            params.append(faction_id)
        return await db.fetchrow(query, *params)
    except ValueError:
        query = """
            SELECT v.id, v.name, v.designation, v.faction_id, v.faction_vehicle_number, v.type,
                   vt.name as type_name
            FROM fleet_vehicles fv
            JOIN vehicles v ON fv.vehicle_id = v.id
            LEFT JOIN vehicle_types vt ON v.type = vt.id
            WHERE fv.fleet_id = $1
              AND (LOWER(v.name) = LOWER($2)
                OR LOWER(CONCAT(v.name, ' ', v.designation)) = LOWER($2))
        """
        return await db.fetchrow(query, fleet_id, identifier)


async def get_vehicle_by_id_or_name(identifier: str, faction_id: int = None) -> dict:
    try:
        vehicle_number = int(identifier)
        if not faction_id:
            return None
        query = """
            SELECT v.id, v.name, v.designation, v.faction_id, v.faction_vehicle_number, v.type,
                   vt.name as type_name
            FROM vehicles v
            LEFT JOIN vehicle_types vt ON v.type = vt.id
            WHERE v.faction_vehicle_number = $1 AND v.faction_id = $2
        """
        return await db.fetchrow(query, vehicle_number, faction_id)
    except ValueError:
        query = """
            SELECT v.id, v.name, v.designation, v.faction_id, v.faction_vehicle_number, v.type,
                   vt.name as type_name
            FROM vehicles v
            LEFT JOIN vehicle_types vt ON v.type = vt.id
            WHERE (LOWER(v.name) = LOWER($1) OR
                   LOWER(CONCAT(v.name, ' ', v.designation)) = LOWER($1))
        """
        params = [identifier]
        if faction_id:
            query += " AND v.faction_id = $2"
            params.append(faction_id)
        return await db.fetchrow(query, *params)
