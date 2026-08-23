# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from datetime import datetime, timezone
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from utils.currency import handle_currency
from services.recruit_service import parse_irp_time
from services.fleet_service import recruit_infantry_to_unit
from repositories.econ_repo import get_resource_ids_by_names
from services.validation_service import require_faction, require_unit


@app_commands.command(name="recruit", description="Recruit infantry into a unit")
@app_commands.describe(
    faction="Faction name",
    unit="Unit ID or name to receive the infantry",
    amount="Amount of personnel (supports k/m/b/t multipliers)",
    individual_cost="Per-person cost, e.g. '100 CM, 50 CS'",
    time="IRP training time, e.g. '2 weeks'",
    name="Role name (default: soldiers)"
)
@require_access_level(0)
@ephemeral_capable('faction')
async def recruit(
    interaction: discord.Interaction,
    faction: str,
    unit: str,
    amount: str,
    individual_cost: str = "",
    time: str = "1 week",
    name: str = "soldiers"
):
    await defer_response(interaction)

    try:
        personnel_amount = int(handle_currency(amount))
        if personnel_amount < 1:
            raise ValueError
    except Exception:
        await interaction.followup.send(embed=error_embed("Error", "Invalid amount."))
        return

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data.id
    faction_color = hex_to_int(faction_data.color)
    display_name = faction_data.display_name

    r_unit_data = await require_unit(unit, faction_id)
    if not r_unit_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_unit_data.error))
    unit_data = r_unit_data.data

    costs = {}
    if individual_cost.strip():
        try:
            for part in individual_cost.split(','):
                tokens = part.strip().split()
                if len(tokens) != 2:
                    raise ValueError
                costs[tokens[1]] = int(tokens[0])
        except Exception:
            await interaction.followup.send(embed=error_embed("Error", "Invalid cost format. Use: '100 CM, 50 CS'"))
            return

    if costs:
        valid = set((await get_resource_ids_by_names(list(costs.keys()))).keys())
        unknown = [n for n in costs if n not in valid]
        if unknown:
            await interaction.followup.send(embed=error_embed("Error", f"Unknown resource(s): {', '.join(unknown)}"))
            return

    completion = datetime.now(timezone.utc) + parse_irp_time(time)

    try:
        await recruit_infantry_to_unit(unit_data['id'], faction_id, personnel_amount, costs, completion)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    unit_label = unit_data['name'] or f"Unit #{unit_data['faction_fleet_number']}"
    cost_display = ", ".join(f"{v * personnel_amount:,} {k}" for k, v in costs.items())
    cost_summary = f"\n**Total Cost:** {cost_display}" if cost_display else ""
    embed = discord.Embed(
        title=f"Military: {display_name}",
        description=f"{display_name} has begun recruiting **{personnel_amount:,} {name}** into **{unit_label}**.{cost_summary}\n\n"
                    f"**Training Time:** {time} (IRP)\n"
                    f"**Ready:** <t:{int(completion.timestamp())}:R>\n\n"
                    f"*Use `/military progress` to check progress*",
        color=faction_color
    )
    await interaction.followup.send(embed=embed)


async def setup(bot):
    pass
