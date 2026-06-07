import time
import discord
from discord import app_commands
from utils.embeds import error_embed, create_embed
from services.scripting.script_service import get_manual_script_by_name, record_execution
from services.scripting.executor import execute_script_manual
from ._helpers import resolve_faction_with_access


@app_commands.command(name="trigger", description="Manually run a TRIGGER script for a faction")
@app_commands.describe(faction="Faction name", name="Script name (must use START ON TRIGGER)")
async def script_trigger(interaction: discord.Interaction, faction: str, name: str):
    await interaction.response.defer()

    faction_data, err = await resolve_faction_with_access(interaction, faction)
    if err:
        await interaction.followup.send(embed=error_embed(err))
        return

    script = await get_manual_script_by_name(faction_data["id"], name)
    if not script:
        await interaction.followup.send(
            embed=error_embed(f"No active TRIGGER script named '{name}' found for {faction_data['display_name']}.")
        )
        return

    start = time.monotonic()
    result = await execute_script_manual(
        script_text=script["script_text"],
        faction_id=faction_data["id"],
        is_company=faction_data.get("is_company", False),
        dry_run=False,
    )
    elapsed_ms = int((time.monotonic() - start) * 1000)

    await record_execution(script["id"], faction_data["id"], result, elapsed_ms)

    if result.aborted:
        description = "Script aborted."
        color = 0xFF0000
    else:
        description = f"{result.actions_taken} action(s) executed."
        color = 0x00CC66

    embed = discord.Embed(
        title=f"Trigger: {script['name']}",
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


async def setup(bot):
    bot.tree.add_command(script_trigger)
