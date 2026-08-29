# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
from typing import Optional
from database.db_manager import db


class StaticCache:
    def __init__(self):
        self.resources: dict[str, dict] = {}
        self.resources_by_id: dict[int, dict] = {}
        self.fleet_status: dict[str, int] = {}
        self.fleet_status_by_id: dict[int, str] = {}
        self.vehicle_types: dict[str, int] = {}
        self.vehicle_types_by_id: dict[int, str] = {}
        self.fleet_types: dict[str, int] = {}
        self.fleet_types_by_id: dict[int, str] = {}
        self.buildings: dict[int, dict] = {}
        self.buildings_by_name: dict[str, dict] = {}
        self.buildings_generators: list[dict] = []
        self.buildings_storages: list[dict] = []
        self.worlds: dict[str, dict] = {}
        self.worlds_by_id: dict[int, dict] = {}
        self.world_resources: dict[int, dict] = {}
        self.loaded: bool = False

    async def load(self):
        resources, fleet_statuses, vehicle_types, fleet_types, buildings, generators, storages, worlds, world_resources = await asyncio.gather(
            db.fetch("SELECT id, name, is_limited, hard_limit FROM resources"),
            db.fetch("SELECT id, name FROM fleet_status"),
            db.fetch("SELECT id, name FROM vehicle_types"),
            db.fetch("SELECT id, name FROM fleet_types"),
            db.fetch("SELECT id, name, description FROM buildings"),
            db.fetch("SELECT building_id, resource_id, production, is_refinery, percentage_affects FROM buildings_generators"),
            db.fetch("SELECT building_id, resource_id, storage FROM buildings_storages"),
            db.fetch("SELECT id, name, hex_count, population_capacity_per_hex, orbit_of FROM worlds"),
            db.fetch("SELECT world_id, resource_id, percentage FROM world_resources"),
        )

        self.resources = {r['name'].lower(): dict(r) for r in resources}
        self.resources_by_id = {r['id']: dict(r) for r in resources}

        self.fleet_status = {s['name'].lower(): s['id'] for s in fleet_statuses}
        self.fleet_status_by_id = {s['id']: s['name'] for s in fleet_statuses}

        self.vehicle_types = {t['name'].lower(): t['id'] for t in vehicle_types}
        self.vehicle_types_by_id = {t['id']: t['name'] for t in vehicle_types}

        self.fleet_types = {t['name'].lower(): t['id'] for t in fleet_types}
        self.fleet_types_by_id = {t['id']: t['name'] for t in fleet_types}

        self.buildings = {b['id']: dict(b) for b in buildings}
        self.buildings_by_name = {b['name'].lower(): dict(b) for b in buildings}

        self.buildings_generators = [dict(r) for r in generators]
        self.buildings_storages = [dict(r) for r in storages]

        self.worlds = {w['name'].lower(): dict(w) for w in worlds}
        self.worlds_by_id = {w['id']: dict(w) for w in worlds}

        wr: dict[int, dict] = {}
        for row in world_resources:
            wid = row['world_id']
            if wid not in wr:
                wr[wid] = {}
            wr[wid][row['resource_id']] = row['percentage']
        self.world_resources = wr

        self.loaded = True

    def get_resource(self, name: str) -> Optional[dict]:
        return self.resources.get(name.lower())

    def get_resource_id(self, name: str) -> Optional[int]:
        r = self.resources.get(name.lower())
        return r['id'] if r else None

    def get_resource_by_id(self, resource_id: int) -> Optional[dict]:
        return self.resources_by_id.get(resource_id)

    def get_world(self, name: str) -> Optional[dict]:
        return self.worlds.get(name.lower())

    def get_world_by_id(self, world_id: int) -> Optional[dict]:
        return self.worlds_by_id.get(world_id)

    def get_fleet_status_id(self, name: str) -> Optional[int]:
        return self.fleet_status.get(name.lower())

    def get_fleet_status_name(self, status_id: int) -> Optional[str]:
        return self.fleet_status_by_id.get(status_id)

    def get_vehicle_type_id(self, name: str) -> Optional[int]:
        return self.vehicle_types.get(name.lower())

    def get_vehicle_type_name(self, type_id: int) -> Optional[str]:
        return self.vehicle_types_by_id.get(type_id)

    def get_fleet_type_id(self, name: str) -> Optional[int]:
        return self.fleet_types.get(name.lower())

    def get_fleet_type_name(self, type_id: int) -> Optional[str]:
        return self.fleet_types_by_id.get(type_id)

    def get_building(self, name: str) -> Optional[dict]:
        return self.buildings_by_name.get(name.lower())

    def get_building_by_id(self, building_id: int) -> Optional[dict]:
        return self.buildings.get(building_id)

    def get_generators_for_building(self, building_id: int) -> list[dict]:
        return [g for g in self.buildings_generators if g['building_id'] == building_id]

    def get_storages_for_building(self, building_id: int) -> list[dict]:
        return [s for s in self.buildings_storages if s['building_id'] == building_id]

    def get_world_resource_percentage(self, world_id: int, resource_id: int) -> float:
        return self.world_resources.get(world_id, {}).get(resource_id, 0.0)


static_cache = StaticCache()
