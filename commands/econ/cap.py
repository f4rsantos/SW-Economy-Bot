# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from utils.currency import handle_return
from services.building_efficiency_service import (
    get_faction_building_count_unweighted,
    calculate_building_cap,
    get_faction_total_hexes
)
from services.building_service import get_company_er
from services.validation_service import require_faction


@app_commands.command(name="cap", description="View faction building cap and growth projections")
@app_commands.describe(faction="Faction name")
@require_access_level(0)
async def cap(interaction: discord.Interaction, faction: str):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data.id
    is_company = faction_data.is_company
    faction_color = hex_to_int(faction_data.color)

    building_count, total_hexes = await asyncio.gather(
        get_faction_building_count_unweighted(faction_id),
        get_faction_total_hexes(faction_id)
    )

    if is_company:
        total_treasury = await get_company_er(faction_id)

        if total_treasury >= 10_000_000_000_000:
            building_cap, next_tier = 600, "Maximum reached"
        elif total_treasury >= 5_000_000_000_000:
            building_cap, next_tier = 500, "10T for 600 cap"
        elif total_treasury >= 1_000_000_000_000:
            building_cap, next_tier = 300, "5T for 500 cap"
        elif total_treasury >= 500_000_000_000:
            building_cap, next_tier = 200, "1T for 300 cap"
        else:
            building_cap, next_tier = 100, "50B for 100 cap"

        usage_pct = int(building_count / building_cap * 100) if building_cap > 0 else 0

        if building_count >= building_cap:
            color = 0xff0000
        elif usage_pct >= 90:
            color = 0xffaa00
        elif usage_pct >= 75:
            color = 0xffff00
        else:
            color = faction_color

        description = (
            f"**Company Status:** Treasury-based building cap\n\n"
            f"**Current Buildings:** {building_count:,} / {building_cap:,}\n"
            f"**Usage:** {usage_pct}%\n"
            f"**Treasury Value:** {handle_return(total_treasury)}\n\n"
            "**Cap Tiers:**\n"
            "• 50B = 100 buildings\n• 500B = 200 buildings\n• 1T = 300 buildings\n"
            "• 5T = 500 buildings\n• 10T+ = 600 buildings (max)\n\n"
        )
        if building_count >= building_cap:
            description += "**At building cap!** Increase treasury to build more."
        elif usage_pct >= 90:
            description += f"**Approaching cap!** Next tier: {next_tier}"
        else:
            description += f"Room for {max(0, building_cap - building_count):,} more building units"
    else:
        building_cap = await calculate_building_cap(faction_id)
        usage_pct = int(building_count / building_cap * 100) if building_cap > 0 else 0

        if building_count >= building_cap and building_cap > 0:
            color = 0xff0000
        elif usage_pct >= 90:
            color = 0xffaa00
        elif usage_pct >= 75:
            color = 0xffff00
        else:
            color = faction_color

        description = (
            f"**Current Buildings:** {building_count:,} / {building_cap:,}\n"
            f"**Usage:** {usage_pct}%\n"
            f"**Territory:** {total_hexes:,} hexes\n\n"
        )
        if building_cap > 0:
            if building_count >= building_cap:
                description += "**At building cap!** Expand territory or remove buildings to build more."
            elif usage_pct >= 90:
                description += "**Approaching cap!** Consider expanding soon."
            else:
                description += f"Room for {max(0, building_cap - building_count):,} more building units (weighted)"
        else:
            description += "**No territory found.** Claim hexes to increase building cap."

    embed = discord.Embed(title=f"Building Cap: {faction_data.display_name}", description=description, color=color)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(cap)
