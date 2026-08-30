# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import io
import logging
from typing import Optional

import discord

logger = logging.getLogger(__name__)

ROUTE_MAP_FILENAME = "solar_map_route.png"
ROUTE_MAP_URL = f"attachment://{ROUTE_MAP_FILENAME}"


async def build_route_map_file(from_world_name: str, to_world_name: str, route_world_names: list) -> Optional[discord.File]:
    try:
        from services.travel_time_service import get_world_system
        from services.solar_map_service import render_solar_map, render_intersystem_route, SolarMapError

        from_system = await get_world_system(from_world_name)
        to_system = await get_world_system(to_world_name)
        if not from_system or not to_system:
            return None

        if from_system != to_system:
            try:
                image_bytes = render_intersystem_route(from_system, to_system, from_world_name, to_world_name)
            except SolarMapError as e:
                logger.warning(f"Route map render failed: {e}")
                return None
            return discord.File(fp=io.BytesIO(image_bytes), filename=ROUTE_MAP_FILENAME)

        try:
            image_bytes, _title, _game_date_label, _closest_body = render_solar_map(
                system_name=from_system,
                route=route_world_names,
            )
        except SolarMapError as e:
            logger.warning(f"Route map render failed: {e}")
            return None

        return discord.File(fp=io.BytesIO(image_bytes), filename=ROUTE_MAP_FILENAME)
    except Exception as e:
        logger.warning(f"Route map render failed unexpectedly: {e}")
        return None
