async def deduct_local_proportional(conn, faction_id: int, resource_id: int, total_available: int, amount: int) -> None:
    if amount <= 0:
        return

    await conn.execute("""
        UPDATE local_treasury lt
        SET amount = lt.amount - FLOOR((lt.amount::FLOAT / $3) * $4)
        WHERE lt.faction_id = $1 AND lt.resource_id = $2 AND lt.amount > 0
    """, faction_id, resource_id, total_available, amount)

    remaining = await conn.fetchval(
        "SELECT COALESCE(SUM(amount), 0) FROM local_treasury WHERE faction_id = $1 AND resource_id = $2",
        faction_id, resource_id
    )
    shortfall = int(remaining) - (int(total_available) - int(amount))
    if shortfall <= 0:
        return

    rows = await conn.fetch("""
        SELECT world_id, amount FROM local_treasury
        WHERE faction_id = $1 AND resource_id = $2 AND amount > 0
        ORDER BY amount DESC
    """, faction_id, resource_id)

    for row in rows:
        if shortfall <= 0:
            break
        take = min(int(row['amount']), shortfall)
        await conn.execute("""
            UPDATE local_treasury SET amount = amount - $4
            WHERE faction_id = $1 AND resource_id = $2 AND world_id = $3
        """, faction_id, resource_id, row['world_id'], take)
        shortfall -= take
