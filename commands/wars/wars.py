# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import json
import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.war_service import get_wars
from services.validation_service import require_faction


@app_commands.command(name="list", description="View all wars, or filter by faction")
@app_commands.describe(faction="Filter by participating faction")
@require_access_level(0)
async def wars(interaction: discord.Interaction, faction: Optional[str] = None):
    await interaction.response.defer()

    faction_color = discord.Color.dark_red()
    faction_data = None

    if faction:
        r_faction_data = await require_faction(faction)
        if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
        faction_data = r_faction_data.data
        faction_color = hex_to_int(faction_data.color)

    if faction_data:
        wars_data = await get_wars(faction_data.id)
        title = f"Wars involving {faction_data.display_name}"
    else:
        wars_data = await get_wars()
        title = "All Active Wars"

    if not wars_data:
        await interaction.followup.send(embed=success_embed("Wars", "No active wars found."))
        return

    embed = discord.Embed(title=title, description=f"{len(wars_data)} active war(s)", color=faction_color)

    for war in wars_data:
        sides_data = war.sides
        if isinstance(sides_data, str):
            try:
                sides_data = json.loads(sides_data)
            except json.JSONDecodeError:
                sides_data = []

        sides_info = {}
        if sides_data:
            for side_obj in sides_data:
                if isinstance(side_obj, str):
                    try:
                        side_obj = json.loads(side_obj)
                    except json.JSONDecodeError:
                        continue
                side = side_obj.get('side')
                factions_list = side_obj.get('factions')
                if side and factions_list:
                    if isinstance(factions_list, str):
                        try:
                            factions_list = json.loads(factions_list)
                        except Exception:
                            pass
                    if isinstance(factions_list, list):
                        sides_info[side] = ', '.join(str(f) for f in factions_list if f)
                    else:
                        sides_info[side] = str(factions_list)

        sides_text = "\n".join(f"**Side {s}:** {f}" for s, f in sorted(sides_info.items())) if sides_info else "No participants yet"
        embed.add_field(
            name=f"War #{war.id} - {war.name}",
            value=f"{sides_text}\n**Battles:** {war.active_battles}\n**Started:** <t:{int(war.date_start.timestamp())}:R>",
            inline=False
        )

    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(wars)
