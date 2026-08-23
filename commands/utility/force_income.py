# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
import logging
import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from services.income_service import execute_income
from services.utility_service import get_status_resource_cache, get_all_factions_min
from services.validation_service import require_faction

logger = logging.getLogger(__name__)

SCOPE_CHOICES = [
    app_commands.Choice(name="Extractors only", value="extractors"),
    app_commands.Choice(name="Extractors + Refineries", value="extractors_refineries"),
    app_commands.Choice(name="Extractors + Refineries + Trade", value="extractors_refineries_trade"),
    app_commands.Choice(name="Extractors + Refineries + Trade + Upkeep", value="extractors_refineries_trade_upkeep"),
    app_commands.Choice(name="Full (+ ER, Influence, Population, Cap)", value="full"),
]


@app_commands.command(name="force-income", description="Force income processing (Level 10 only)")
@app_commands.describe(
    faction="Faction name to process income for (leave blank for all factions)",
    scope="How much of the income cycle to run",
)
@app_commands.choices(scope=SCOPE_CHOICES)
@require_access_level(10)
async def force_income(
    interaction: discord.Interaction,
    scope: app_commands.Choice[str],
    faction: str = None,
):
    await interaction.response.defer()

    shared_cache = await get_status_resource_cache()
    scope_value = scope.value

    if faction:
        r_faction_data = await require_faction(faction)
        if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
        faction_data = r_faction_data.data

        faction_id = faction_data.id
        faction_name = faction_data.display_name

        try:
            logger.info(f"[FORCE-INCOME] Triggered by {interaction.user} for faction: {faction_name} (scope={scope_value})")
            await execute_income(faction_id, shared_cache, scope=scope_value)
            logger.info(f"[FORCE-INCOME] Complete for {faction_name}")
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(embed=error_embed("Error", f"Income processing failed for **{faction_name}**:\n```{e}```"))
            return

        await interaction.followup.send(embed=success_embed("Income Processed", f"Income cycle (`{scope.name}`) processed for **{faction_name}**."))
        return

    factions = await get_all_factions_min()
    logger.info(f"[FORCE-INCOME] Triggered by {interaction.user} for ALL factions (scope={scope_value}, count={len(factions)})")

    async def _run_one(row):
        f_id = row['id']
        f_name = row['name']
        try:
            await execute_income(f_id, shared_cache, scope=scope_value)
            logger.info(f"[FORCE-INCOME] Complete for {f_name}")
            return None
        except Exception as e:
            logger.exception(f"[FORCE-INCOME] FAILED for {f_name}: {e}")
            return f_name

    results = await asyncio.gather(*[_run_one(r) for r in factions])
    failed = [n for n in results if n]

    if failed:
        await interaction.followup.send(embed=error_embed(
            "Partial Failure",
            f"Income cycle (`{scope.name}`) completed with errors for:\n" + "\n".join(f"- **{n}**" for n in failed),
        ))
    else:
        await interaction.followup.send(embed=success_embed(
            "Income Processed",
            f"Income cycle (`{scope.name}`) successfully processed for all **{len(factions)}** factions.",
        ))


async def setup(bot):
    bot.tree.add_command(force_income)
