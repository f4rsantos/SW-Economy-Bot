import asyncpg


class DatabaseManager:
    def __init__(self):
        self.pool = None
        self.database_url = None

    def set_database_url(self, database_url: str):
        self.database_url = database_url

    async def connect(self):
        if not self.database_url:
            raise RuntimeError("DatabaseManager.set_database_url() must be called before connect()")
        if not self.pool:
            import ssl
            import certifi
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=5,
                max_size=20,
                ssl=ssl_context,
                statement_cache_size=0
            )
            print("Database pool created successfully")

    async def disconnect(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def _ensure_connected(self):
        if not self.pool:
            await self.connect()

    async def fetch(self, query, *args):
        await self._ensure_connected()
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query, *args):
        await self._ensure_connected()
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query, *args):
        await self._ensure_connected()
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def execute(self, query, *args):
        await self._ensure_connected()
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def executemany(self, query, args_list):
        await self._ensure_connected()
        async with self.pool.acquire() as conn:
            return await conn.executemany(query, args_list)

    def get_connection(self):
        if not self.pool:
            raise Exception("Database not connected")
        return self.pool.acquire()


db = DatabaseManager()
