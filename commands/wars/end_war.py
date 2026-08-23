# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from utils.date_utils import pretty_date
from services.war_service import end_war, get_war, get_participant
from services.validation_service import require_faction


def _parse_sides(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    return [s.strip().upper() for s in raw.split(',') if s.strip()]


@app_commands.command(name="end", description="End a war and all its battles")
@app_commands.describe(
    war_id="ID of the war to end",
    faction="Your faction name",
    winning_sides="Comma-separated sides that won (optional, can be left blank)",
    losing_sides="Comma-separated sides that lost (optional, can be left blank)",
)
@require_access_level(0)
async def end_war_cmd(interaction: discord.Interaction, war_id: int, faction: str, winning_sides: Optional[str] = None, losing_sides: Optional[str] = None):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data.color)

    war_data = await get_war(war_id)
    if not war_data:
        await interaction.followup.send(embed=error_embed("Error", "War not found."))
        return

    if not await get_participant(war_id, faction_data.id):
        await interaction.followup.send(embed=error_embed("Error", "Your faction must be a participant to end this war."))
        return

    try:
        result = await end_war(war_id, faction_data.id, _parse_sides(winning_sides), _parse_sides(losing_sides))
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    def _label(side: str) -> str:
        if side in result['winning_sides']:
            return ' (Victorious)'
        if side in result['losing_sides']:
            return ' (Recovering)'
        return ''

    stats_text = "\n".join(f"**Side {s['side']}{_label(s['side'])}:** {', '.join(s['faction_names'])}" for s in result['stats'])

    now = discord.utils.utcnow()
    time_diff = now - war_data.date_start
    days = time_diff.days
    hours, remainder = divmod(time_diff.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes or not parts:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    duration = f"\n**Duration:** {pretty_date(war_data.date_start)} - {pretty_date(now)} ({', '.join(parts)})"

    embed = success_embed(
        title="War Ended",
        description=f"**{war_data.name}** has been ended.{duration}\n**Total Battles:** {result['total_battles']} (Deleted)\n\n**Participants:**\n{stats_text}\n\nWinning sides gain **Victorious** (+10% Efficiency), losing sides gain **Recovering** (+50% Efficiency), both through the next income cycle. Sides left out of both lists get no bonus."
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(end_war_cmd)
