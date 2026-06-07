import logging
import re
from datetime import datetime, timezone, timedelta
from database.db_manager import db

logger = logging.getLogger(__name__)

IRP_MONTH_TO_DAYS = 7 / 3
IRP_WEEK_TO_DAYS = IRP_MONTH_TO_DAYS / 4

_TIME_PATTERNS = [
    (r'(\d+(?:\.\d+)?)\s*(?:years?|y)', 12 * IRP_MONTH_TO_DAYS),
    (r'(\d+(?:\.\d+)?)\s*(?:months?|mo)', IRP_MONTH_TO_DAYS),
    (r'(\d+(?:\.\d+)?)\s*(?:weeks?|w)', IRP_WEEK_TO_DAYS),
    (r'(\d+(?:\.\d+)?)\s*(?:days?|d)', IRP_WEEK_TO_DAYS / 7),
]


def parse_irp_time(time_str: str) -> timedelta:
    total_days = 0.0
    s = time_str.lower().strip()
    for pattern, multiplier in _TIME_PATTERNS:
        for match in re.findall(pattern, s):
            total_days += float(match) * multiplier
    return timedelta(days=total_days if total_days > 0 else IRP_WEEK_TO_DAYS)


async def create_recruitment(faction_id: int, amount: int, irp_time_str: str, role_name: str = "soldiers", fleet_id: int = None) -> dict:
    start_time = datetime.now(timezone.utc)
    completion_time = start_time + parse_irp_time(irp_time_str)
    result = await db.fetchrow("""
        INSERT INTO military_recruitment (faction_id, amount, role_name, start_time, completion_time, status)
        VALUES ($1, $2, $3, $4, $5, 'training')
        RETURNING id, faction_id, amount, role_name, start_time, completion_time, status
    """, faction_id, amount, role_name, start_time, completion_time)
    row = dict(result) if result else None
    if row:
        from services.event_queue import event_queue
        await event_queue.push(completion_time, 'recruitment_complete', {
            'recruitment_id': row['id'], 'fleet_id': fleet_id, 'amount': amount
        })
    return row


async def get_pending_recruitments(faction_id: int) -> list:
    rows = await db.fetch("""
        SELECT mr.id, mr.faction_id, mr.amount, mr.role_name,
               mr.start_time, mr.completion_time, mr.status, mr.fleet_id,
               f.name as unit_name, f.faction_fleet_number as unit_number
        FROM military_recruitment mr
        LEFT JOIN fleets f ON mr.fleet_id = f.id
        WHERE mr.faction_id = $1 AND mr.status = 'training'
        ORDER BY mr.completion_time ASC
    """, faction_id)
    return [dict(row) for row in rows]


async def get_all_pending_recruitments() -> list:
    rows = await db.fetch("""
        SELECT mr.id, mr.faction_id, mr.amount, mr.role_name,
               mr.start_time, mr.completion_time, mr.status, mr.fleet_id,
               fac.name as faction_name, f.name as unit_name, f.faction_fleet_number as unit_number
        FROM military_recruitment mr
        JOIN factions fac ON mr.faction_id = fac.id
        LEFT JOIN fleets f ON mr.fleet_id = f.id
        WHERE mr.status = 'training'
        ORDER BY mr.completion_time ASC
    """)
    return [dict(row) for row in rows]


async def process_completed_recruitments() -> list:
    current_time = datetime.now(timezone.utc)
    completed = await db.fetch(
        "SELECT id, faction_id, amount, role_name, fleet_id FROM military_recruitment WHERE status = 'training' AND completion_time <= $1",
        current_time
    )
    if not completed:
        return []

    processed = []
    for r in completed:
        try:
            if r['fleet_id']:
                await db.execute(
                    "UPDATE fleets SET infantry_count = infantry_count + $1 WHERE id = $2",
                    r['amount'], r['fleet_id']
                )
            await db.execute("DELETE FROM military_recruitment WHERE id = $1", r['id'])
            processed.append({'faction_id': r['faction_id'], 'amount': r['amount'], 'role_name': r['role_name'], 'fleet_id': r['fleet_id']})
            logger.info(f"Recruitment complete: {r['amount']:,} {r['role_name']} for faction {r['faction_id']} → unit {r['fleet_id']}")
        except Exception as e:
            logger.error(f"Error processing recruitment {r['id']}: {e}")
    return processed


async def cancel_recruitment(recruitment_id: int, faction_id: int) -> dict | None:
    row = await db.fetchrow("""
        DELETE FROM military_recruitment
        WHERE id = $1 AND faction_id = $2 AND status = 'training'
        RETURNING id, amount, role_name
    """, recruitment_id, faction_id)
    return dict(row) if row else None


async def format_time_remaining(completion_time: datetime) -> str:
    now = datetime.now(timezone.utc)
    remaining = completion_time - now
    if remaining.total_seconds() <= 0:
        return "Ready!"
    days = remaining.days
    hours, rem = divmod(remaining.seconds, 3600)
    minutes = rem // 60
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 and days == 0:
        parts.append(f"{minutes}m")
    return " ".join(parts) if parts else "< 1m"
