# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import math
import re
from datetime import datetime, timedelta
from typing import Optional

from services import orbital_config as config
from services.travel_time_service import get_absolute_position_3d, get_config_key
from services.orbital_config import IRL_SECONDS_PER_GAME_YEAR
from utils.date_utils import get_solar_date, is_leap_year

SOLAR_EPOCH = datetime(2023, 5, 1)
SOLAR_EPOCH_YEAR = 2123
SUPERSAMPLE = 2
BASE_SIZE = 1600
FOCUS_SIZE = 1400
MARGIN = 90


class SolarMapError(ValueError):
    pass


def resolve_system(system_name: str) -> tuple[str, dict]:
    for key in config.SYSTEMS_DATA:
        if key.lower() == system_name.strip().lower():
            return key, config.SYSTEMS_DATA[key]
    raise SolarMapError(f"Unknown system '{system_name}'. Valid systems: {', '.join(config.SYSTEMS_DATA.keys())}")


def resolve_body(body_name: str, system_data: dict) -> str:
    key = get_config_key(body_name, system_data)
    if not key:
        raise SolarMapError(f"Unknown body '{body_name}' in this system.")
    return key



def parse_game_date(date_str: str) -> datetime:
    parts = date_str.strip().split("-")
    if len(parts) != 3:
        raise SolarMapError(f"Invalid date '{date_str}'. Use format yyyy-mm-dd (in-game date).")
    try:
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        raise SolarMapError(f"Invalid date '{date_str}'. Use format yyyy-mm-dd (in-game date).")
    if not (1 <= month <= 12):
        raise SolarMapError(f"Invalid month '{month}'. Must be between 1 and 12.")
    if day < 1 or day > 31:
        raise SolarMapError(f"Invalid day '{day}'. Must be between 1 and 31.")
    return _solar_to_real(year, month, day)


def _solar_to_real(year: int, month: int, day: int) -> datetime:
    total_months = year - SOLAR_EPOCH_YEAR
    real_month_index = (SOLAR_EPOCH.month - 1) + total_months
    real_year = SOLAR_EPOCH.year + real_month_index // 12
    real_month = real_month_index % 12 + 1

    month_start = datetime(real_year, real_month, 1)
    month_end = datetime(real_year + 1, 1, 1) if real_month == 12 else datetime(real_year, real_month + 1, 1)
    year_len = (month_end - month_start).total_seconds() - 1

    leap = is_leap_year(year)
    months = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if leap:
        months[1] = 29
    if month > 12 or day > months[month - 1]:
        raise SolarMapError(f"Invalid day '{day}' for month '{month}'.")

    day_count = sum(months[: month - 1]) + day
    days_in_year = 366 if leap else 365
    fraction = min((day_count + 0.5) / days_in_year, 1.0)
    point_seconds = fraction * year_len
    return month_start + timedelta(seconds=point_seconds)


def current_game_date_str(now: Optional[datetime] = None) -> str:
    year, month, day = get_solar_date(now)
    return f"{year:04d}-{month:02d}-{day:02d}"



def _is_top_level(name: str, data: dict) -> bool:
    return data.get("parent") is None


def list_pageable_bodies(system_name: str) -> list[str]:
    canonical_system, system_data = resolve_system(system_name)
    bodies = [name for name, data in system_data.items() if _is_top_level(name, data)]
    bodies = [name for name in bodies if "Asteroid Belt" not in name]
    bodies.sort(key=lambda name: (system_data[name].get("a", system_data[name].get("dist", 0)), name))
    return bodies


def list_focus_bodies(system_name: str, focus_name: str) -> list[str]:
    canonical_system, system_data = resolve_system(system_name)
    canonical_focus = resolve_body(focus_name, system_data)
    moons = [name for name, data in system_data.items() if data.get("parent") == canonical_focus]
    moons.sort(key=lambda name: system_data[name].get("a", system_data[name].get("dist", 0)))
    return [canonical_focus] + moons


def _overview_radius_fn(system_data: dict, bodies: list[str], mode: str, zoom: float, dists: dict, max_radius_px: float):
    perihelions = []
    aphelions = []
    for name in bodies:
        data = system_data[name]
        a = data.get("a", data.get("dist", 1.0))
        e = data.get("e", 0.0)
        perihelions.append(a * (1.0 - e))
        aphelions.append(a * (1.0 + e))

    min_dist = (min(perihelions) * 0.75) if perihelions else 0.2
    max_dist = (max(aphelions) * 1.05) if aphelions else 45.0

    if mode == "log":
        min_radius_px = 90 * SUPERSAMPLE

        def radius_px(d):
            d = max(d, min_dist)
            t = (math.log(d) - math.log(min_dist)) / (math.log(max_dist) - math.log(min_dist)) if max_dist > min_dist else 0.0
            return (min_radius_px + (max_radius_px - min_radius_px) * t) * zoom
    else:
        current_max = max(dists.values()) if dists else 1.0
        px_per_au = (max_radius_px / current_max) * zoom if current_max > 0 else 1.0

        def radius_px(d):
            return d * px_per_au

    return radius_px


def _focus_radius_fn(system_data: dict, moons: list[str], focus_name: str, zoom: float, max_radius_px: float):
    moon_perihelions = []
    moon_aphelions = []
    for name in moons:
        data = system_data[name]
        a = data.get("a", data.get("dist", 0.005))
        e = data.get("e", 0.0)
        moon_perihelions.append(a * (1.0 - e))
        moon_aphelions.append(a * (1.0 + e))

    min_dist = (min(moon_perihelions) * 0.75) if moon_perihelions else 0.0005
    max_dist = (max(moon_aphelions) * 1.05) if moon_aphelions else 0.03

    size_scale = _radius_scale_for_bodies(list(system_data.keys()), system_data)
    planet_t = size_scale.get(focus_name, 0.6)
    planet_icon_size = int(_icon_size_for(planet_t) * 1.6 * SUPERSAMPLE * min(zoom, 1.5))
    inner_radius_px = max(90 * SUPERSAMPLE, planet_icon_size * 1.05)

    def moon_radius_px(dist):
        dist = max(dist, min_dist)
        if max_dist > min_dist:
            t = (math.log(dist) - math.log(min_dist)) / (math.log(max_dist) - math.log(min_dist))
        else:
            t = 1.0
        return (inner_radius_px + (max_radius_px - inner_radius_px) * t) * zoom

    return moon_radius_px


def center_pan_for_body(
    system_name: str,
    body_name: str,
    date_str: Optional[str] = None,
    mode: str = "log",
    zoom: float = 1.0,
    focus: Optional[str] = None,
) -> tuple[float, float]:
    canonical_system, system_data = resolve_system(system_name)

    if date_str:
        when = parse_game_date(date_str)
    else:
        when = datetime.now()

    mode = (mode or "log").lower()
    zoom = max(0.1, min(zoom or 1.0, 20.0))

    if focus:
        canonical_focus = resolve_body(focus, system_data)
        canonical_body = resolve_body(body_name, system_data)
        if canonical_body == canonical_focus:
            return 0.0, 0.0

        size = FOCUS_SIZE * SUPERSAMPLE
        max_radius_px = size / 2 - MARGIN * SUPERSAMPLE

        moons = [name for name, data in system_data.items() if data.get("parent") == canonical_focus]
        focus_pos = get_absolute_position_3d(canonical_focus, when, system_data)
        pos = get_absolute_position_3d(canonical_body, when, system_data)
        rel_x, rel_y = pos.x - focus_pos.x, pos.y - focus_pos.y
        dist = math.hypot(rel_x, rel_y)
        angle = math.atan2(rel_y, rel_x)

        moon_radius_px = _focus_radius_fn(system_data, moons, canonical_focus, zoom, max_radius_px)
        r_px = min(moon_radius_px(dist), max_radius_px)
    else:
        canonical_body = resolve_body(body_name, system_data)
        bodies = [name for name, data in system_data.items() if _is_top_level(name, data)]
        positions = {name: get_absolute_position_3d(name, when, system_data) for name in bodies}
        dists = {name: math.hypot(positions[name].x, positions[name].y) for name in bodies}

        pos = positions[canonical_body]
        angle = math.atan2(pos.y, pos.x)
        overview_max_radius_px = BASE_SIZE * SUPERSAMPLE / 2 - MARGIN * SUPERSAMPLE
        radius_px = _overview_radius_fn(system_data, bodies, mode, zoom, dists, overview_max_radius_px)
        r_px = radius_px(dists[canonical_body])

    pan_x = -r_px * math.cos(angle) / SUPERSAMPLE
    pan_y = -r_px * math.sin(angle) / SUPERSAMPLE
    return pan_x, pan_y




BODY_RADII_KM = {
    "Mercury": 2440, "Venus": 6052, "Earth": 6371, "Mars": 3390,
    "Jupiter": 69911, "Saturn": 58232, "Uranus": 25362, "Neptune": 24622,
    "Pluto": 1188, "Ceres": 473,
    "Luna": 1737,
    "Io": 1822, "Europa": 1561, "Ganymede": 2634, "Callisto": 2410,
    "Mimas": 198, "Enceladus": 252, "Tethys": 531, "Dione": 561,
    "Rhea": 764, "Titan": 2575, "Iapetus": 735,
    "Miranda": 236, "Ariel": 579, "Umbriel": 585, "Titania": 789, "Oberon": 761,
    "Proteus": 210, "Triton": 1353, "Nereid": 170,
    "Charon": 606,
    "Barcas": 5800, "Deo Gloria": 4200, "Novai": 7100, "Scipios": 3100,
    "Vesta": 263,
}
DEFAULT_BODY_RADIUS_KM = 3000


def _radius_scale_for_bodies(bodies: list[str], system_data: dict) -> dict:
    if not bodies:
        return {}
    radii = [BODY_RADII_KM.get(b, DEFAULT_BODY_RADIUS_KM) for b in bodies]
    min_r, max_r = min(radii), max(radii)
    scale = {}
    for b in bodies:
        r = BODY_RADII_KM.get(b, DEFAULT_BODY_RADIUS_KM)
        if max_r > min_r:
            t = (math.log(r) - math.log(min_r)) / (math.log(max_r) - math.log(min_r))
        else:
            t = 0.5
        scale[b] = t
    return scale


PLANET_ICON_MIN = 26
PLANET_ICON_MAX = 64
MOON_ICON_MIN = 30
MOON_ICON_MAX = 60


def _icon_size_for(t: float, is_moon: bool = False) -> int:
    lo, hi = (MOON_ICON_MIN, MOON_ICON_MAX) if is_moon else (PLANET_ICON_MIN, PLANET_ICON_MAX)
    return int(lo + (hi - lo) * t)
