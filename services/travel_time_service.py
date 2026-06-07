import math
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
from dataclasses import dataclass

from database.db_manager import db
import services.orbital_config as config


@dataclass
class Vector2:
    x: float
    y: float


def get_current_angle(world_data: dict, current_time: datetime) -> float:
    epoch = datetime.fromisoformat(config.ALIGNMENT_EPOCH_STR)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    time_diff = (current_time - epoch).total_seconds()
    angle = world_data.get('angle', 0.0) + (world_data['speed'] * time_diff)
    return angle % (2 * math.pi)


def get_absolute_position(world_name: str, current_time: datetime, system_data: Dict) -> Vector2:
    data = system_data.get(world_name)
    if not data:
        return Vector2(0.0, 0.0)
    angle = get_current_angle(data, current_time)
    local_x = data['dist'] * math.cos(angle)
    local_y = data['dist'] * math.sin(angle)
    parent_name = data.get('parent')
    if parent_name:
        parent_pos = get_absolute_position(parent_name, current_time, system_data)
        return Vector2(local_x + parent_pos.x, local_y + parent_pos.y)
    return Vector2(local_x, local_y)


def get_config_key(name: str, data_dict: Dict) -> Optional[str]:
    name_lower = name.lower()
    for key in data_dict:
        if key.lower() == name_lower:
            return key
    return None


async def get_world_system(world_name: str) -> Optional[str]:
    if get_config_key(world_name, config.SOL_ORBITAL_DATA):
        return "Sol"
    if get_config_key(world_name, config.CORELLI_ORBITAL_DATA):
        return "Corelli"
    result = await db.fetchrow("""
        WITH RECURSIVE world_tree AS (
            SELECT id, name, orbit_of, 0 as depth FROM worlds WHERE LOWER(name) = LOWER($1)
            UNION ALL
            SELECT w.id, w.name, w.orbit_of, wt.depth + 1
            FROM worlds w INNER JOIN world_tree wt ON w.id = wt.orbit_of
            WHERE wt.depth < 10
        )
        SELECT name FROM world_tree ORDER BY depth DESC LIMIT 1
    """, world_name)
    if result:
        root = result['name']
        if root in ["Sun", "Sol"] or get_config_key(root, config.SOL_ORBITAL_DATA):
            return "Sol"
        if root in ["Corelli Star", "Corelli"] or get_config_key(root, config.CORELLI_ORBITAL_DATA):
            return "Corelli"
    return None


async def calculate_travel_time(from_world: str, to_world: str, current_time: Optional[datetime] = None) -> timedelta:
    if current_time is None:
        current_time = datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    if from_world.lower() == to_world.lower():
        return timedelta(minutes=15)

    from_sys = await get_world_system(from_world)
    to_sys = await get_world_system(to_world)

    if from_sys != to_sys:
        return timedelta(days=config.INTER_SYSTEM_TRAVEL_DAYS)

    system_data = config.SYSTEMS_DATA.get(from_sys)
    if not system_data:
        return timedelta(hours=1)

    from_canonical = get_config_key(from_world, system_data) or from_world
    to_canonical = get_config_key(to_world, system_data) or to_world

    pos_a = get_absolute_position(from_canonical, current_time, system_data)
    pos_b = get_absolute_position(to_canonical, current_time, system_data)
    distance = math.sqrt((pos_b.x - pos_a.x) ** 2 + (pos_b.y - pos_a.y) ** 2)

    speed = config.CALIBRATION_DISTANCE_UNITS / config.CALIBRATION_TIME_HOURS
    hours = min(distance / speed, 336)
    if hours <= 0.0167:
        return timedelta(0)
    return timedelta(hours=hours)


async def format_travel_time(travel_time: timedelta) -> str:
    total = int(travel_time.total_seconds())
    days = total // 86400
    hours = (total % 86400) // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0 and days == 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds > 0 and days == 0 and hours == 0:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    return ", ".join(parts) if parts else "0 seconds"
