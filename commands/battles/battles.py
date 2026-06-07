import asyncio
import json
import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.battle_service import get_battles
from services.validation_service import require_faction, require_world


def _parse_sides(sides_raw) -> str:
    if isinstance(sides_raw, str):
        try:
            sides_raw = json.loads(sides_raw)
        except json.JSONDecodeError:
            return "No participants yet"
    sides_info = {}
    for side_obj in (sides_raw or []):
        if isinstance(side_obj, str):
            try:
                side_obj = json.loads(side_obj)
            except json.JSONDecodeError:
                continue
        side = side_obj.get('side')
        if side and side not in sides_info:
            factions_list = side_obj.get('factions', [])
            if isinstance(factions_list, str):
                try:
                    factions_list = json.loads(factions_list)
                except Exception:
                    factions_list = []
            sides_info[side] = {
                'count': side_obj.get('count', 0),
                'cs': side_obj.get('cs', 0),
                'factions': ', '.join(str(f) for f in factions_list if f) if factions_list else 'Unknown'
            }
    if not sides_info:
        return "No participants yet"
    return "\n".join(f"Side {s}: {d['factions']} - {d['count']} fleet(s), {int(d['cs'])} CS" for s, d in sorted(sides_info.items()))


@app_commands.command(name="battles", description="View all battles by faction or world")
@app_commands.describe(faction="Filter by participating faction", world="Filter by battle location")
@require_access_level(0)
async def battles(interaction: discord.Interaction, faction: Optional[str] = None, world: Optional[str] = None):
    await interaction.response.defer()

    faction_data = None
    world_data = None
    faction_color = discord.Color.red()

    if faction and world:
        r_faction_data, r_world_data = await asyncio.gather(require_faction(faction), require_world(world))
        if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
        if not r_world_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_world_data.error))
        faction_data = r_faction_data.data
        faction_color = hex_to_int(faction_data['color'])
        world_data = r_world_data.data
    elif faction:
        r_faction_data = await require_faction(faction)
        if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
        faction_data = r_faction_data.data
        faction_color = hex_to_int(faction_data['color'])
    elif world:
        r_world_data = await require_world(world)
        if not r_world_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_world_data.error))
        world_data = r_world_data.data

    faction_id = faction_data['id'] if faction_data else None
    world_id = world_data['id'] if world_data else None

    battles_data = await get_battles(faction_id=faction_id, world_id=world_id)

    if faction_data and world_data:
        title = f"Battles at {world_data['name']} involving {faction_data['display_name']}"
    elif faction_data:
        title = f"Battles involving {faction_data['display_name']}"
    elif world_data:
        title = f"Battles at {world_data['name']}"
    else:
        title = "All Active Battles"

    if not battles_data:
        await interaction.followup.send(embed=success_embed("Battles", "No active battles found."))
        return

    embed = discord.Embed(title=title, description=f"{len(battles_data)} active battle(s)", color=faction_color)
    for battle in battles_data:
        war_info = f" (War #{battle['war_id']})" if battle['war_id'] else ""
        sides_text = _parse_sides(battle['sides'])
        embed.add_field(
            name=f"Battle #{battle['id']} - {battle['world_name']}{war_info}",
            value=f"{sides_text}\n**Started:** <t:{int(battle['date_start'].timestamp())}:R>",
            inline=False
        )

    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(battles)
