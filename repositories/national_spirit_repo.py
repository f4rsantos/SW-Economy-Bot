# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from database.db_manager import db
from dtos.national_spirit import NationalSpirit


async def get_active_efficiency_bonus(faction_id: int) -> float:
    row = await db.fetchrow(
        """
        SELECT COALESCE(SUM(ns.modifier_value), 0) as total
        FROM national_spirits ns
        JOIN spirit_types st ON ns.spirit_type_id = st.id
        WHERE ns.faction_id = $1 AND st.effect_type = 'efficiency'
        """,
        faction_id,
    )
    return float(row['total']) if row else 0.0


async def get_active_factory_efficiency_bonus(faction_id: int) -> float:
    row = await db.fetchrow(
        """
        SELECT COALESCE(SUM(ns.modifier_value), 0) as total
        FROM national_spirits ns
        JOIN spirit_types st ON ns.spirit_type_id = st.id
        WHERE ns.faction_id = $1 AND st.effect_type = 'efficiency_factory'
        """,
        faction_id,
    )
    return float(row['total']) if row else 0.0


async def get_national_spirits(faction_id: int) -> list[NationalSpirit]:
    rows = await db.fetch(
        """
        SELECT st.display_name, st.effect_type, ns.modifier_value, ns.granted_at, ns.expires_at
        FROM national_spirits ns
        JOIN spirit_types st ON ns.spirit_type_id = st.id
        WHERE ns.faction_id = $1
        ORDER BY ns.granted_at
        """,
        faction_id,
    )
    return NationalSpirit.from_rows(rows)
