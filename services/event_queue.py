# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
import heapq
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

LOOKAHEAD = timedelta(hours=2)

DB_BACKED_EVENTS = {'transfer_arrival', 'construction_complete', 'recruitment_complete', 'fleet_arrival', 'income_cycle'}


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
        if event_type in DB_BACKED_EVENTS:
            now = datetime.now(timezone.utc)
            if due_at > now + LOOKAHEAD:
                return
        async with self._lock:
            self._counter += 1
            heapq.heappush(self._heap, (due_at.timestamp(), self._counter, event_type, payload))

    async def push_income_event(self):
        from repositories import event_queue_repo
        settings = await event_queue_repo.get_settings()
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
        from repositories import event_queue_repo
        from services.travel_time_service import calculate_travel_time

        now = datetime.now(timezone.utc)
        horizon = now + LOOKAHEAD

        transfers = await event_queue_repo.get_due_transfers(horizon)
        constructions = await event_queue_repo.get_due_constructions(horizon)
        recruitments = await event_queue_repo.get_due_recruitments(horizon)
        moving_fleets = await event_queue_repo.get_moving_fleets()

        async with self._lock:
            self._heap = [e for e in self._heap if e[2] not in DB_BACKED_EVENTS]
            heapq.heapify(self._heap)

        for t in transfers:
            arrival = await event_queue_repo.get_transfer_arrival_time(t['id'])
            if arrival:
                await self.push(arrival, 'transfer_arrival', {'transfer_id': t['id'], 'to_faction_id': t['to_faction_id'], 'to_world_id': t['to_world_id']})

        for c in constructions:
            due = await event_queue_repo.get_construction_completion_date(c['id'])
            if due:
                await self.push(max(due, now), 'construction_complete', {'order_id': c['id'], 'fleet_id': c['fleet_id'], 'vehicle_id': c['vehicle_id'], 'quantity': c['quantity']})

        for r in recruitments:
            due = await event_queue_repo.get_recruitment_completion_time(r['id'])
            if due:
                await self.push(max(due, now), 'recruitment_complete', {'recruitment_id': r['id'], 'fleet_id': r['fleet_id'], 'amount': r['amount']})

        for fleet in moving_fleets:
            try:
                travel_time = await calculate_travel_time(fleet['from_world'], fleet['to_world'])
                moving_since = fleet['moving_since']
                if moving_since.tzinfo is None:
                    moving_since = moving_since.replace(tzinfo=timezone.utc)
                arrival = moving_since + travel_time
                if arrival <= horizon:
                    await self.push(max(arrival, now), 'fleet_arrival', {'fleet_id': fleet['id'], 'to_world_id': fleet['moving_to']})
            except Exception:
                logger.exception(f"EventQueue: failed to schedule arrival for fleet #{fleet['id']}")

        await self.push_income_event()

    @property
    def is_running(self) -> bool:
        return self._running

    def queue_size(self) -> int:
        return len(self._heap)

    async def _safe_load_window(self) -> bool:
        try:
            await self.load_window()
            return True
        except Exception:
            logger.exception("EventQueue: load_window failed, retrying in 60s")
            return False

    async def worker(self):
        self._running = True
        ok = await self._safe_load_window()
        next_reload = datetime.now(timezone.utc) + (LOOKAHEAD if ok else timedelta(seconds=60))

        while self._running:
            now = datetime.now(timezone.utc)

            if now >= next_reload:
                ok = await self._safe_load_window()
                next_reload = now + (LOOKAHEAD if ok else timedelta(seconds=60))

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
