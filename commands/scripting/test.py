# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed, create_embed
from services.scripting.script_service import get_script_by_name
from services.scripting.executor import execute_script, execute_script_manual
from utils.scripting_helpers import resolve_faction_with_access


@app_commands.command(name="test", description="Dry-run a faction script without executing any actions")
@app_commands.describe(faction="Faction name", name="Script name")
@require_access_level(0)
async def script_test(interaction: discord.Interaction, faction: str, name: str):
    await interaction.response.defer()

    faction_data, err = await resolve_faction_with_access(interaction, faction)
    if err:
        await interaction.followup.send(embed=error_embed(err))
        return

    script = await get_script_by_name(faction_data.id, name)
    if not script:
        await interaction.followup.send(
            embed=error_embed(f"No active script named '{name}'.")
        )
        return

    runner = execute_script_manual if script.trigger_type == "manual" else execute_script
    result = await runner(
        script_text=script.script_text,
        faction_id=faction_data.id,
        is_company=faction_data.is_company,
        dry_run=True,
    )

    if result.skipped:
        description = "Script would be skipped today (START ON day does not match)."
        color = 0x808080
    elif result.aborted:
        description = "Script aborted during dry-run."
        color = 0xFF0000
    else:
        description = f"Dry-run complete. {result.actions_taken} action(s) would fire."
        color = 0x00AAFF

    embed = discord.Embed(
        title=f"Dry-Run: {script.name}",
        description=description,
        color=color,
    )

    if result.errors:
        embed.add_field(
            name="Errors",
            value="\n".join(f"`{e}`" for e in result.errors[:5]),
            inline=False,
        )

    if result.warnings:
        embed.add_field(
            name="Warnings",
            value="\n".join(result.warnings[:5]),
            inline=False,
        )

    await interaction.followup.send(embed=embed)
