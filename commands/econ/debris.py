import asyncio
import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import error_embed
from services.faction_service import search_faction_names
from services.map_service import search_world_names
from services.fleet_service import list_debris_fleets
from services.validation_service import require_faction, require_world


class DebrisGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="debris", description="Manage debris")

debris_group = DebrisGroup()


async def faction_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    names = await search_faction_names(current, 25)
    return [app_commands.Choice(name=name, value=name) for name in names]


async def world_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    names = await search_world_names(current, 25)
    return [app_commands.Choice(name=name, value=name) for name in names]


@debris_group.command(name="list", description="List all debris fleets")
@app_commands.describe(faction="Filter by faction", world="Filter by world")
@require_access_level(0)
async def debris_list(interaction: discord.Interaction, faction: Optional[str] = None, world: Optional[str] = None):
    await interaction.response.defer()

    faction_id = None
    world_id = None

    if faction and world:
        r_faction_data, r_world = await asyncio.gather(require_faction(faction), require_world(world))
        if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
        if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
        faction_id = r_faction_data.data['id']
        world_id = r_world.data['id']
    elif faction:
        r_faction_data = await require_faction(faction)
        if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
        faction_id = r_faction_data.data['id']
    elif world:
        r_world = await require_world(world)
        if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
        world_id = r_world.data['id']

    rows = await list_debris_fleets(faction_id=faction_id, world_id=world_id)

    if not rows:
        filter_text = (f" for {faction}" if faction else "") + (f" at {world}" if world else "")
        await interaction.followup.send(embed=error_embed("No Debris Found", f"No debris fleets found{filter_text}."))
        return

    LIMIT = 20
    lines = []
    for r in rows[:LIMIT]:
        fname = r['name'] or f"Fleet #{r['faction_fleet_number']}"
        lines.append(f"**{r['faction_name']}** — {fname} (ID: {r['faction_fleet_number']}) at **{r['world_name']}** • {r['total_cs']:,} CS")
    footer = f"Total: {len(rows)}" + (f" • Showing top {LIMIT}" if len(rows) > LIMIT else "")

    embed = discord.Embed(title="Debris", description="\n".join(lines), color=0x95a5a6)
    embed.set_footer(text=footer)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(debris_group)
    cmd = debris_group.get_command('list')
    if cmd:
        cmd.autocomplete('faction')(faction_autocomplete)
        cmd.autocomplete('world')(world_autocomplete)
