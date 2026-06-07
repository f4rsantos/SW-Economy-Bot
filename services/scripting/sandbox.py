\
\
\
\
\
\
from __future__ import annotations
import math
from datetime import datetime, timezone, timedelta
from typing import Optional

from database.db_manager import db
from services.map_service import get_world, get_world_by_id
from services.transfer_service import (
    check_blockade,
    execute_er_transfer,
    execute_physical_transfer,
    has_world_presence,
    get_local_resource_amount,
)
from services.econ_query_service import get_global_resource_amount
from services.fleet_service import (
    get_fleet,
    move_fleet,
    set_fleet_status,
    buy_vehicle,
    get_factory_info,
    get_vehicle_length,
    get_vehicle_cost_rows,
)
from services.building_service import buy_building, get_building, get_building_by_name
from services.transfer_service import upgrade_buildings
from services.recruit_service import create_recruitment, parse_irp_time
from utils.faction_utils import get_faction_by_name


class FALSandbox:
    def __init__(self, faction_id: int, is_company: bool = False, dry_run: bool = False):
        assert isinstance(faction_id, int), "faction_id must be an integer"
        self._faction_id = faction_id
        self._is_company = is_company
        self._dry_run = dry_run

    @property
    def faction_id(self) -> int:
        return self._faction_id


    async def get_resource_amount(self, resource_name: str) -> int:
        """Return own faction's total of a resource. Local resources are summed across all worlds."""
        LOCAL_RESOURCES = {"CM", "CS", "EL", "U-CM", "U-CS", "U-EL", "POPULATION"}
        GLOBAL_RESOURCES = {"ER", "MILITARY", "INFLUENCE"}

        res_upper = resource_name.upper()

        if res_upper in LOCAL_RESOURCES:
            row = await db.fetchrow(
                """SELECT COALESCE(SUM(lt.amount), 0) as total
                   FROM local_treasury lt
                   JOIN resources r ON lt.resource_id = r.id
                   WHERE lt.faction_id = $1 AND UPPER(r.name) = $2""",
                self._faction_id, res_upper,
            )
            return int(row["total"]) if row else 0

        if res_upper in GLOBAL_RESOURCES:
            db_name = res_upper.capitalize() if res_upper != "ER" else "ER"
            row = await db.fetchrow(
                """SELECT COALESCE(ft.amount, 0) as total
                   FROM faction_treasury ft
                   JOIN resources r ON ft.resource_id = r.id
                   WHERE ft.faction_id = $1 AND UPPER(r.name) = $2""",
                self._faction_id, res_upper,
            )
            return int(row["total"]) if row else 0

        return 0

    async def get_fleet_health(self, fleet_id: int) -> int:
        row = await db.fetchrow(
            "SELECT health FROM fleets WHERE id = $1 AND faction_id = $2",
            fleet_id, self._faction_id,
        )
        if not row:
            raise ValueError(f"Fleet {fleet_id} not found or does not belong to your faction")
        return int(row["health"])

    async def get_fleet_status_name(self, fleet_id: int) -> str:
        row = await db.fetchrow(
            """SELECT fs.name FROM fleets f
               JOIN fleet_status fs ON f.status_id = fs.id
               WHERE f.id = $1 AND f.faction_id = $2""",
            fleet_id, self._faction_id,
        )
        if not row:
            raise ValueError(f"Fleet {fleet_id} not found or does not belong to your faction")
        return row["name"].upper()

    async def get_building_count(self, building_id: int, world_id: int) -> int:
        row = await db.fetchrow(
            """SELECT COALESCE(amount, 0) as total
               FROM faction_world_buildings
               WHERE faction_id = $1 AND building_id = $2 AND world_id = $3""",
            self._faction_id, building_id, world_id,
        )
        return int(row["total"]) if row else 0

    async def is_at_war(self) -> bool:
        row = await db.fetchrow(
            "SELECT 1 FROM war_participants WHERE faction_id = $1 LIMIT 1",
            self._faction_id,
        )
        return row is not None

    async def is_blockaded(self, world_id: int) -> bool:
        return await check_blockade(world_id, self._faction_id)

    async def get_current_day_name(self) -> str:
        """Return current UTC weekday as canonical day name e.g. MONDAY."""
        days = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
        return days[datetime.now(timezone.utc).weekday()]

    async def resolve_world(self, ref) -> dict:
        """Resolve a world name (str) or ID (int) to a world dict. Raises ValueError if not found."""
        if isinstance(ref, int):
            world = await get_world_by_id(ref)
        else:
            world = await get_world(str(ref))
        if not world:
            raise ValueError(f"World '{ref}' not found")
        return dict(world)

    async def resolve_fleet(self, ref) -> dict:
        """Resolve a fleet number (int) or name (str) to a fleet dict scoped to own faction."""
        if isinstance(ref, int):
            row = await db.fetchrow(
                """SELECT f.id, f.name, f.faction_fleet_number, f.health, f.total_cs,
                          f.position, fs.name as status_name, w.name as world_name
                   FROM fleets f
                   JOIN fleet_status fs ON f.status_id = fs.id
                   JOIN worlds w ON f.position = w.id
                   WHERE f.faction_id = $1 AND (f.id = $2 OR f.faction_fleet_number = $2)""",
                self._faction_id, ref,
            )
        else:
            row = await db.fetchrow(
                """SELECT f.id, f.name, f.faction_fleet_number, f.health, f.total_cs,
                          f.position, fs.name as status_name, w.name as world_name
                   FROM fleets f
                   JOIN fleet_status fs ON f.status_id = fs.id
                   JOIN worlds w ON f.position = w.id
                   WHERE f.faction_id = $1 AND LOWER(f.name) = LOWER($2)""",
                self._faction_id, str(ref),
            )
        if not row:
            raise ValueError(f"Fleet '{ref}' not found or does not belong to your faction")
        return dict(row)

    async def resolve_building(self, ref) -> dict:
        """Resolve a building ID (int) or name (str) from the buildings catalog."""
        if isinstance(ref, int):
            building = await get_building(ref)
        else:
            building = await get_building_by_name(str(ref))
        if not building:
            raise ValueError(f"Building '{ref}' not found")
        return building

    async def resolve_faction(self, ref: str) -> dict:
        """Resolve a faction name to a faction dict. Used for TRANSFER destination."""
        faction = await get_faction_by_name(str(ref))
        if not faction:
            raise ValueError(f"Faction '{ref}' not found")
        return faction

    async def resolve_vehicle(self, ref) -> dict:
        """Resolve a vehicle by number (int) or name (str) scoped to own faction."""
        if isinstance(ref, int):
            row = await db.fetchrow(
                """SELECT v.id, v.name, v.designation, v.faction_vehicle_number
                   FROM vehicles v
                   WHERE v.faction_id = $1 AND v.faction_vehicle_number = $2""",
                self._faction_id, ref,
            )
        else:
            row = await db.fetchrow(
                """SELECT v.id, v.name, v.designation, v.faction_vehicle_number
                   FROM vehicles v
                   WHERE v.faction_id = $1
                     AND (LOWER(v.name) = LOWER($2)
                       OR LOWER(CONCAT(v.name, ' ', v.designation)) = LOWER($2))""",
                self._faction_id, str(ref),
            )
        if not row:
            raise ValueError(f"Vehicle '{ref}' not found or does not belong to your faction")
        return dict(row)

    async def get_factory_space_available(self, world_id: int) -> int:
        """Return available (unused) factory space at a world for own faction, in metres."""
        total_capacity, used_space = await get_factory_info(world_id, self._faction_id, is_large=False)
        return max(0, total_capacity - used_space)

    async def get_fleets_at_world(self, world_id: int) -> list[int]:
        """Return list of fleet IDs at the given world belonging to own faction."""
        rows = await db.fetch(
            "SELECT id FROM fleets WHERE faction_id = $1 AND position = $2 ORDER BY faction_fleet_number",
            self._faction_id, world_id,
        )
        return [r["id"] for r in rows]

    async def get_fleets_at_world_for_faction(self, world_id: int, faction_id: int) -> list[int]:
        rows = await db.fetch(
            "SELECT id FROM fleets WHERE faction_id = $1 AND position = $2 ORDER BY faction_fleet_number",
            faction_id, world_id,
        )
        return [r["id"] for r in rows]

    async def resolve_fleet_for_faction(self, ref, faction_id: int) -> dict:
        if isinstance(ref, int):
            row = await db.fetchrow(
                """SELECT f.id, f.name, f.faction_fleet_number, f.health, f.total_cs,
                          f.position, fs.name as status_name, w.name as world_name
                   FROM fleets f
                   JOIN fleet_status fs ON f.status_id = fs.id
                   JOIN worlds w ON f.position = w.id
                   WHERE f.faction_id = $1 AND (f.id = $2 OR f.faction_fleet_number = $2)""",
                faction_id, ref,
            )
        else:
            row = await db.fetchrow(
                """SELECT f.id, f.name, f.faction_fleet_number, f.health, f.total_cs,
                          f.position, fs.name as status_name, w.name as world_name
                   FROM fleets f
                   JOIN fleet_status fs ON f.status_id = fs.id
                   JOIN worlds w ON f.position = w.id
                   WHERE f.faction_id = $1 AND LOWER(f.name) = LOWER($2)""",
                faction_id, str(ref),
            )
        if not row:
            raise ValueError(f"Fleet '{ref}' not found for the specified faction")
        return dict(row)

    async def get_fleet_vehicle_count(self, fleet_id: int) -> int:
        row = await db.fetchrow(
            "SELECT COALESCE(SUM(amount), 0) as total FROM fleet_vehicles WHERE fleet_id = $1",
            fleet_id,
        )
        return int(row["total"]) if row else 0

    async def get_world_resource_amount(self, world_id: int, resource_name: str) -> int:
        row = await db.fetchrow(
            """SELECT COALESCE(lt.amount, 0) as total
               FROM local_treasury lt
               JOIN resources r ON lt.resource_id = r.id
               WHERE lt.faction_id = $1 AND lt.world_id = $2 AND UPPER(r.name) = $3""",
            self._faction_id, world_id, resource_name.upper(),
        )
        return int(row["total"]) if row else 0

    async def get_resource_id(self, resource_name: str) -> Optional[int]:
        row = await db.fetchrow(
            "SELECT id FROM resources WHERE UPPER(name) = $1",
            resource_name.upper(),
        )
        return row["id"] if row else None


    async def do_transfer(
        self,
        amount: int,
        resource_name: str,
        from_world_id: int,
        from_world_name: str,
        to_faction_id: int,
        to_world_id: int,
        to_world_name: str,
        current_time: datetime,
    ) -> str:
        """Transfer resources from own faction to another faction."""
        if self._dry_run:
            return f"[dry-run] TRANSFER {amount:,} {resource_name} → faction {to_faction_id} at {to_world_name}"

        if resource_name.upper() == "ER":
            er_id = await self.get_resource_id("ER")
            current = await get_global_resource_amount(self._faction_id, er_id)
            if current < amount:
                raise ValueError(f"Insufficient ER: need {amount:,}, have {current:,}")
            await execute_er_transfer(
                self._faction_id, to_faction_id,
                from_world_id, to_world_id,
                er_id, amount, current_time,
            )
            return f"Transferred {amount:,} ER to faction {to_faction_id}"

        resource_id = await self.get_resource_id(resource_name)
        if not resource_id:
            raise ValueError(f"Unknown resource '{resource_name}'")

        have = await get_local_resource_amount(from_world_id, self._faction_id, resource_id)
        if have < amount:
            raise ValueError(f"Insufficient {resource_name} at {from_world_name}: need {amount:,}, have {have:,}")

        if await check_blockade(from_world_id, self._faction_id):
            raise ValueError(f"{from_world_name} is blockaded and cannot send transfers")
        if await check_blockade(to_world_id, to_faction_id):
            raise ValueError(f"Destination {to_world_name} is blockaded and cannot receive transfers")

        transfers = [{"resource": resource_name, "amount": amount}]
        resource_map = {resource_name: resource_id}
        result = await execute_physical_transfer(
            self._faction_id, to_faction_id,
            from_world_id, to_world_id,
            from_world_name, to_world_name,
            transfers, resource_map, current_time,
        )
        return f"Transfer {result['transfer_id']} in transit, arrives {result['arrival_time'].isoformat()}"

    async def do_buy_building(
        self,
        building_id: int,
        amount: int,
        world_id: int,
        level: int,
    ) -> str:
        if self._dry_run:
            return f"[dry-run] BUY BUILDING {building_id} x{amount} at world {world_id} level {level}"
        result = await buy_building(
            self._faction_id, world_id, building_id, amount, level, self._is_company
        )
        costs_str = ", ".join(f"{v:,} {k}" for k, v in result["costs"].items())
        return f"Bought {amount}x {result['building_name']} (level {level}). Cost: {costs_str}"

    async def do_upgrade_building(
        self,
        building_id: int,
        amount: int,
        world_id: int,
        from_level: int,
        to_level: int,
    ) -> str:
        if self._dry_run:
            return f"[dry-run] UPGRADE BUILDING {building_id} x{amount} at world {world_id} from level {from_level} to {to_level}"
        import json
        costs = {}
        try:
            await upgrade_buildings(
                self._faction_id, world_id, building_id, amount, from_level, to_level, costs
            )
        except ValueError as e:
            raise
        return f"Upgraded {amount}x building {building_id} from level {from_level} to {to_level}"

    async def do_move_fleet(
        self,
        fleet_id: int,
        fleet_world_name: str,
        dest_world_id: int,
        dest_world_name: str,
        current_time: datetime,
    ) -> str:
        fleet = await get_fleet(fleet_id)
        if not fleet or fleet["faction_id"] != self._faction_id:
            raise ValueError(f"Fleet {fleet_id} not found or does not belong to your faction")

        if self._dry_run:
            return f"[dry-run] MOVE FLEET {fleet_id} to {dest_world_name}"

        from services.travel_time_service import calculate_travel_time
        await move_fleet(fleet_id, dest_world_id, current_time)
        return f"Fleet {fleet_id} moving to {dest_world_name}"

    async def do_fleet_status(self, fleet_id: int, status_name: str) -> str:
        fleet = await get_fleet(fleet_id)
        if not fleet or fleet["faction_id"] != self._faction_id:
            raise ValueError(f"Fleet {fleet_id} not found or does not belong to your faction")

        if self._dry_run:
            return f"[dry-run] FLEET STATUS {fleet_id} → {status_name}"

        await set_fleet_status(fleet_id, status_name)
        return f"Fleet {fleet_id} status set to {status_name}"

    async def do_buy_vehicles(
        self,
        vehicle_id: int,
        fleet_id: int,
        amount: int,
        current_time: datetime,
    ) -> str:
        fleet = await get_fleet(fleet_id)
        if not fleet or fleet["faction_id"] != self._faction_id:
            raise ValueError(f"Fleet {fleet_id} not found or does not belong to your faction")

        world_id = fleet["position"]
        vehicle_length = await get_vehicle_length(vehicle_id)
        costs = await get_vehicle_cost_rows(vehicle_id)
        if not costs:
            raise ValueError(f"Vehicle {vehicle_id} has no cost defined")

        total_factory_space = vehicle_length * amount
        is_large = vehicle_length > 1000
        total_capacity, used_space = await get_factory_info(world_id, self._faction_id, is_large)
        available = total_capacity - used_space

        if total_factory_space > available:
            if is_large and total_capacity > 0:
                weeks_needed = math.ceil(total_factory_space / total_capacity)
            else:
                raise ValueError(
                    f"Insufficient factory space: need {total_factory_space:,.0f}m, have {available:,.0f}m"
                )
        else:
            weeks_needed = 1

        completion = current_time + timedelta(weeks=weeks_needed)
        costs_list = [{"name": c["name"], "amount": c["amount"]} for c in costs]

        if self._dry_run:
            cost_str = ", ".join(f"{c['amount'] * amount:,} {c['name']}" for c in costs)
            return f"[dry-run] BUY VEHICLES {amount}x vehicle {vehicle_id} for fleet {fleet_id}. Cost: {cost_str}"

        order_id = await buy_vehicle(
            self._faction_id, world_id, fleet_id,
            vehicle_id, amount, int(total_factory_space), completion, costs_list,
        )
        return f"Construction order {order_id} placed: {amount}x vehicle {vehicle_id} for fleet {fleet_id}"

    async def do_recruit(
        self,
        amount: int,
        cost_per_unit: int,
        resource_name: str,
        duration: str,
        name: str,
    ) -> str:
        if self._dry_run:
            return f"[dry-run] RECRUIT MILITARY {amount:,} COST {cost_per_unit:,} {resource_name} NAME '{name}'"

        total_cost = amount * cost_per_unit
        resource_id = await self.get_resource_id(resource_name)
        if not resource_id:
            raise ValueError(f"Unknown resource '{resource_name}'")

        LOCAL_RESOURCES = {"CM", "CS", "EL", "U-CM", "U-CS", "U-EL", "POPULATION"}
        if resource_name.upper() in LOCAL_RESOURCES:
            row = await db.fetchrow(
                """SELECT world_id FROM local_treasury
                   WHERE faction_id = $1 AND resource_id = $2 AND amount >= $3
                   ORDER BY amount DESC LIMIT 1""",
                self._faction_id, resource_id, total_cost,
            )
            if not row:
                raise ValueError(f"Insufficient {resource_name} for recruitment cost {total_cost:,}")
            await db.execute(
                "UPDATE local_treasury SET amount = amount - $1 WHERE faction_id = $2 AND world_id = $3 AND resource_id = $4",
                total_cost, self._faction_id, row["world_id"], resource_id,
            )
        else:
            row = await db.fetchrow(
                "SELECT amount FROM faction_treasury WHERE faction_id = $1 AND resource_id = $2",
                self._faction_id, resource_id,
            )
            current = int(row["amount"]) if row else 0
            if current < total_cost:
                raise ValueError(f"Insufficient {resource_name}: need {total_cost:,}, have {current:,}")
            await db.execute(
                "UPDATE faction_treasury SET amount = amount - $1 WHERE faction_id = $2 AND resource_id = $3",
                total_cost, self._faction_id, resource_id,
            )

        result = await create_recruitment(self._faction_id, amount, duration, name)
        return f"Recruitment '{name}' started: {amount:,} troops, completes at {result['completion_time'].isoformat()}"
