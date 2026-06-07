import asyncio
from typing import Dict, Optional
from database.db_manager import db


class CacheManager:
    def __init__(self, refresh_interval=300):
        self.cache: Dict[str, Dict] = {}
        self.users: Dict[int, Dict] = {}
        self.refresh_interval = refresh_interval
        self.running = False

    async def load_full_cache(self):
        self.cache['factions'] = {
            row['id']: {**dict(row), 'display_name': row['formal_name'] or row['name']}
            for row in await db.fetch("SELECT * FROM factions")
        }
        self.users = {row['id']: dict(row) for row in await db.fetch("SELECT * FROM users")}
        self.cache['players'] = self.users
        custom_messages_rows = await db.fetch("SELECT user_id, message FROM custom_user_messages")
        self.cache['custom_messages'] = {row['user_id']: row['message'] for row in custom_messages_rows}

    async def start_refresh_loop(self):
        self.running = True
        while self.running:
            await asyncio.sleep(self.refresh_interval)
            await self.load_full_cache()

    def stop(self):
        self.running = False

    def get_faction(self, faction_id: int) -> Optional[Dict]:
        return self.cache.get('factions', {}).get(faction_id)

    def get_all_factions(self) -> Dict:
        return self.cache.get('factions', {})

    def set_faction(self, faction_id: int, data: dict):
        if 'factions' not in self.cache:
            self.cache['factions'] = {}
        self.cache['factions'][faction_id] = data

    def invalidate_faction(self, faction_id: int):
        self.cache.get('factions', {}).pop(faction_id, None)

    def get_player(self, user_id: int) -> Optional[Dict]:
        return self.cache.get('players', {}).get(user_id)

    def get_user(self, user_id: int) -> Optional[Dict]:
        return self.users.get(user_id)

    def get_custom_message(self, user_id: int) -> Optional[str]:
        return self.cache.get('custom_messages', {}).get(user_id)

    def set_custom_message(self, user_id: int, msg: Optional[str]):
        if 'custom_messages' not in self.cache:
            self.cache['custom_messages'] = {}
        if msg is not None:
            self.cache['custom_messages'][user_id] = msg
        else:
            self.cache['custom_messages'].pop(user_id, None)


cache = CacheManager()
cache_manager = cache
