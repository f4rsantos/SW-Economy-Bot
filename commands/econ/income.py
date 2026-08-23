# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from utils.currency import handle_return
from services.income_service import preview_income
from services.map_service import get_worlds_by_ids
from services.validation_service import require_faction, require_world


def _fmt(amount: int) -> str:
    return f"{'+'if amount > 0 else ''}{handle_return(amount)}"


@app_commands.command(name="income", description="Preview next income cycle")
@app_commands.describe(faction="Faction name", world="Specific world to view", resource="Resource name — shows per-world income")
@require_access_level(0)
async def income(
    interaction: discord.Interaction,
    faction: str,
    world: str = None,
    resource: Optional[str] = None
):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data.id
    faction_color = hex_to_int(faction_data.color)

    if resource:
        res_name = resource.upper()
        preview = await preview_income(faction_id)
        world_amounts = {}
        for w_id, w_data in preview['worlds'].items():
            if res_name == 'CS':
                amount = w_data.get('net_cs_pre_upkeep', 0)
            else:
                amount = next((v for k, v in w_data.get('final', {}).items() if k.upper() == res_name), 0)
            if amount != 0:
                world_amounts[w_id] = amount

        if not world_amounts:
            await interaction.followup.send(embed=error_embed("Error", f"No income data for `{res_name}` on any world."))
            return

        world_rows = await get_worlds_by_ids(list(world_amounts.keys()))
        name_map = {r['id']: r['name'] for r in world_rows}
        sorted_worlds = sorted(world_amounts.items(), key=lambda x: x[1], reverse=True)
        total = 0
        lines = []
        for w_id, amount in sorted_worlds:
            lines.append(f"**{name_map.get(w_id, f'World {w_id}')}**: {_fmt(amount)}")
            total += amount

        embed = discord.Embed(
            title=f"Income ({res_name}): {faction_data.display_name} per World",
            description="\n".join(lines), color=faction_color
        )
        embed.set_footer(text=f"Total: {_fmt(total)}")
        await interaction.followup.send(embed=embed)
        return

    if world:
        r_world = await require_world(world)
        if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
        world_data = r_world.data

        preview = await preview_income(faction_id)
        if world_data['id'] not in preview['worlds']:
            await interaction.followup.send(embed=error_embed("Error", f"No income data found for world '{world}'."))
            return

        final = preview['worlds'][world_data['id']].get('final', {})
        lines = [f"**{r}:** {_fmt(final[r])}" for r in ['U-CM', 'U-EL', 'U-CS', 'CM', 'EL', 'CS'] if final.get(r)]
        embed = discord.Embed(title=world_data['name'], description="\n".join(lines) if lines else "No production", color=faction_color)
        await interaction.followup.send(embed=embed)
        return

    preview = await preview_income(faction_id)
    totals: dict = {}
    for w_data in preview['worlds'].values():
        for res, amount in w_data.get('final', {}).items():
            totals[res] = totals.get(res, 0) + amount

    for transfer in preview.get('transfers', []):
        if transfer['to_faction_id'] == faction_id and transfer.get('resource_name'):
            totals[transfer['resource_name']] = totals.get(transfer['resource_name'], 0) + transfer.get('amount', 0)

    for trade in preview['usages'].get('external_incoming_trades', []):
        totals[trade['resource_name']] = totals.get(trade['resource_name'], 0) + trade['amount']

    fleet_cs = preview['usages'].get('fleet_cs', 0)
    pop_cs = sum(preview['usages'].get('population_cs', {}).values())
    gross_cs = sum(w.get('gross_cs', 0) for w in preview['worlds'].values())
    totals['CS'] = gross_cs - pop_cs - fleet_cs

    totals['ER'] = preview['global']['er']
    totals['Influence'] = preview['global']['influence']

    total_pop_delta = sum(w.get('population_growth', 0) for w in preview['worlds'].values())

    lines = [f"**{r}:** {_fmt(totals[r])}" for r in ['ER', 'U-CM', 'U-EL', 'U-CS', 'CM', 'EL', 'CS', 'Influence'] if totals.get(r)]
    if fleet_cs > 0 or pop_cs > 0:
        lines.append(f"**CS Upkeep:** -{handle_return(fleet_cs + pop_cs)} (Fleet: {handle_return(fleet_cs)} + Pop: {handle_return(pop_cs)})")
    if total_pop_delta != 0:
        lines.append(f"**Population:** {_fmt(total_pop_delta)}")

    embed = discord.Embed(
        title=f"Income: {faction_data.display_name}",
        description="\n".join(lines) if lines else "No income",
        color=faction_color
    )
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(income)
