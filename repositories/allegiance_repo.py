# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import List, Optional

from database.db_manager import db
from dtos.allegiance_request import AllegianceRequest


async def create_request(user_id: int, faction_id: int) -> AllegianceRequest:
    await db.execute(
        """
        UPDATE allegiance_requests SET status = 'denied', resolved_at = now()
        WHERE user_id = $1 AND status = 'pending'
        """,
        user_id,
    )
    row = await db.fetchrow(
        """
        INSERT INTO allegiance_requests (user_id, faction_id)
        VALUES ($1, $2)
        RETURNING *
        """,
        user_id,
        faction_id,
    )
    return AllegianceRequest.from_row(row)


async def get_pending_request_for_user(user_id: int) -> Optional[AllegianceRequest]:
    row = await db.fetchrow(
        "SELECT * FROM allegiance_requests WHERE user_id = $1 AND status = 'pending'",
        user_id,
    )
    return AllegianceRequest.from_row(row) if row else None


async def get_request_by_id(request_id: int) -> Optional[AllegianceRequest]:
    row = await db.fetchrow("SELECT * FROM allegiance_requests WHERE id = $1", request_id)
    return AllegianceRequest.from_row(row) if row else None


async def get_pending_requests_for_faction(faction_id: int) -> List[AllegianceRequest]:
    rows = await db.fetch(
        """
        SELECT * FROM allegiance_requests
        WHERE faction_id = $1 AND status = 'pending'
        ORDER BY requested_at ASC
        """,
        faction_id,
    )
    return AllegianceRequest.from_rows(rows)


async def resolve_request(request_id: int, status: str, resolved_by: int) -> Optional[AllegianceRequest]:
    row = await db.fetchrow(
        """
        UPDATE allegiance_requests
        SET status = $2, resolved_at = now(), resolved_by = $3
        WHERE id = $1 AND status = 'pending'
        RETURNING *
        """,
        request_id,
        status,
        resolved_by,
    )
    return AllegianceRequest.from_row(row) if row else None
