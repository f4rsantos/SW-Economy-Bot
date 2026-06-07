import asyncio
import heapq
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

LOOKAHEAD = timedelta(hours=2)


class EventQueue:
    def __init__(self):
        self._heap: list[tuple[float, int, str, dict]] = []
        self._counter = 0
        self._lock = asyncio.Lock()
        self._handlers: dict[str, Callable[..., Awaitable]] = {}
        self._running = False

    def register_handler(self, event_type: str, handler: Callable[..., Awaitable]):
        self._handlers[event_type] = handler

    async def push(self, due_at: datetime, event_type: str, payload: dict):
        now = datetime.now(timezone.utc)
        if due_at <= now + LOOKAHEAD:
            async with self._lock:
                self._counter += 1
                heapq.heappush(self._heap, (due_at.timestamp(), self._counter, event_type, payload))

    async def push_income_event(self):
        from database.db_manager import db
        settings = await db.fetchrow("SELECT last_income, income_day FROM settings LIMIT 1")
        if not settings:
            return
        last_income = settings['last_income']
        income_day = settings['income_day'] or 6
        if not last_income:
            return
        target_weekday = income_day - 1
        now = datetime.now(timezone.utc)
        next_check = last_income
        while next_check <= now + timedelta(hours=2):
            next_check += timedelta(days=1)
            if next_check.weekday() == target_weekday:
                await self.push(next_check, 'income_cycle', {})
                return

    async def load_window(self):
        from database.db_manager import db
        from services.travel_time_service import calculate_travel_time

        now = datetime.now(timezone.utc)
        horizon = now + LOOKAHEAD

        transfers = await db.fetch(
            "SELECT id, to_faction_id, to_world_id FROM resource_transfers WHERE status = 'in_transit' AND arrival_time BETWEEN $1 AND $2",
            now, horizon
        )
        constructions = await db.fetch(
            "SELECT id, fleet_id, vehicle_id, quantity FROM vehicle_construction WHERE completion_date <= $1",
            horizon
        )
        recruitments = await db.fetch(
            "SELECT id, faction_id, amount, role_name, fleet_id FROM military_recruitment WHERE status = 'training' AND completion_time <= $1",
            horizon
        )
        moving_fleets = await db.fetch(
            """
            SELECT f.id, f.moving_since, f.moving_to, w1.name as from_world, w2.name as to_world
            FROM fleets f
            JOIN worlds w1 ON f.position = w1.id
            JOIN worlds w2 ON f.moving_to = w2.id
            WHERE f.moving_to IS NOT NULL AND f.moving_since IS NOT NULL
            """
        )

        async with self._lock:
            self._heap.clear()
            self._counter = 0

        for t in transfers:
            arrival = await db.fetchval("SELECT arrival_time FROM resource_transfers WHERE id = $1", t['id'])
            if arrival:
                await self.push(arrival, 'transfer_arrival', {'transfer_id': t['id'], 'to_faction_id': t['to_faction_id'], 'to_world_id': t['to_world_id']})

        for c in constructions:
            due = await db.fetchval("SELECT completion_date FROM vehicle_construction WHERE id = $1", c['id'])
            if due:
                await self.push(max(due, now), 'construction_complete', {'order_id': c['id'], 'fleet_id': c['fleet_id'], 'vehicle_id': c['vehicle_id'], 'quantity': c['quantity']})

        for r in recruitments:
            due = await db.fetchval("SELECT completion_time FROM military_recruitment WHERE id = $1", r['id'])
            if due:
                await self.push(max(due, now), 'recruitment_complete', {'recruitment_id': r['id'], 'fleet_id': r['fleet_id'], 'amount': r['amount']})

        for fleet in moving_fleets:
            try:
                travel_time = await calculate_travel_time(fleet['from_world'], fleet['to_world'])
                moving_since = fleet['moving_since']
                if moving_since.tzinfo is None:
                    moving_since = moving_since.replace(tzinfo=timezone.utc)
                arrival = moving_since + travel_time
                if now <= arrival <= horizon:
                    await self.push(arrival, 'fleet_arrival', {'fleet_id': fleet['id'], 'to_world_id': fleet['moving_to']})
            except Exception:
                pass

        await self.push_income_event()

    async def worker(self):
        self._running = True
        await self.load_window()
        next_reload = datetime.now(timezone.utc) + LOOKAHEAD

        while self._running:
            now = datetime.now(timezone.utc)

            if now >= next_reload:
                await self.load_window()
                next_reload = now + LOOKAHEAD

            due_item = None
            async with self._lock:
                if self._heap and self._heap[0][0] <= now.timestamp():
                    _, _, event_type, payload = heapq.heappop(self._heap)
                    due_item = (event_type, payload)

            if due_item:
                event_type, payload = due_item
                handler = self._handlers.get(event_type)
                if handler:
                    try:
                        await handler(payload)
                    except Exception as e:
                        logger.exception(f"EventQueue handler error [{event_type}]: {e}")
            else:
                async with self._lock:
                    next_due = self._heap[0][0] if self._heap else None
                wait = 1.0
                if next_due:
                    wait = min(30.0, max(0.1, next_due - datetime.now(timezone.utc).timestamp()))
                else:
                    wait = 30.0
                await asyncio.sleep(wait)

    def stop(self):
        self._running = False


event_queue = EventQueue()
