from utils.result import Result
from utils.faction_utils import get_faction_by_id
from utils.fleet_utils import get_fleet_by_id_or_name, get_vehicle_by_id_or_name
from database.static_cache import static_cache


async def require_faction(name: str) -> Result:
    from utils.faction_utils import get_faction
    data = await get_faction(name)
    return Result.success(data) if data else Result.fail(f"Faction '{name}' not found.")


async def require_faction_by_id(faction_id: int) -> Result:
    data = await get_faction_by_id(faction_id)
    return Result.success(data) if data else Result.fail(f"Faction ID {faction_id} not found.")


async def require_world(name: str) -> Result:
    data = static_cache.get_world(name)
    if not data:
        from services.map_service import get_world
        data = await get_world(name)
    return Result.success(data) if data else Result.fail(f"World '{name}' not found.")


async def require_unit(identifier: str, faction_id: int) -> Result:
    data = await get_fleet_by_id_or_name(identifier, faction_id)
    return Result.success(data) if data else Result.fail(f"Unit '{identifier}' not found.")


async def require_vehicle(identifier: str, faction_id: int) -> Result:
    data = await get_vehicle_by_id_or_name(identifier, faction_id)
    return Result.success(data) if data else Result.fail(f"Vehicle '{identifier}' not found.")


async def require_resource(name: str) -> Result:
    data = static_cache.get_resource(name)
    return Result.success(data) if data else Result.fail(f"Resource '{name}' not found.")


async def require_badge(identifier: str) -> Result:
    from services.utility_service import get_badge_by_identifier
    data = await get_badge_by_identifier(identifier)
    return Result.success(data) if data else Result.fail(f"Badge '{identifier}' not found.")
