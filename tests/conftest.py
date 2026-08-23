# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import pytest
from database.db_manager import db


class FakeDB:
    def __init__(self):
        self.fetch_queue = []
        self.fetchrow_queue = []
        self.fetchval_queue = []
        self.executed = []

    async def fetch(self, query, *args):
        self.executed.append(("fetch", query, args))
        return self.fetch_queue.pop(0) if self.fetch_queue else []

    async def fetchrow(self, query, *args):
        self.executed.append(("fetchrow", query, args))
        return self.fetchrow_queue.pop(0) if self.fetchrow_queue else None

    async def fetchval(self, query, *args):
        self.executed.append(("fetchval", query, args))
        return self.fetchval_queue.pop(0) if self.fetchval_queue else None

    async def execute(self, query, *args):
        self.executed.append(("execute", query, args))
        return "OK"


@pytest.fixture
def fake_db(monkeypatch):
    fake = FakeDB()
    monkeypatch.setattr(db, "fetch", fake.fetch)
    monkeypatch.setattr(db, "fetchrow", fake.fetchrow)
    monkeypatch.setattr(db, "fetchval", fake.fetchval)
    monkeypatch.setattr(db, "execute", fake.execute)
    return fake
