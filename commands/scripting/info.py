import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed, create_embed
from services.scripting.script_service import get_script_by_name
from utils.scripting_helpers import resolve_faction_with_access


@app_commands.command(name="info", description="Show details of a faction script")
@app_commands.describe(faction="Faction name", name="Script name")
@require_access_level(0)
async def script_info(interaction: discord.Interaction, faction: str, name: str):
    await interaction.response.defer()

    faction_data, err = await resolve_faction_with_access(interaction, faction)
    if err:
        await interaction.followup.send(embed=error_embed(err))
        return

    script = await get_script_by_name(faction_data["id"], name)
    if not script:
        await interaction.followup.send(embed=error_embed(f"No active script named '{name}'."))
        return

    runs_on = "Manual Trigger" if script["trigger_type"] == "manual" else (script["trigger_day"] or "Income Day")
    last_run = f"<t:{int(script['last_run_at'].timestamp())}:F>" if script["last_run_at"] else "Never"
    created = f"<t:{int(script['created_at'].timestamp())}:F>"
    updated = f"<t:{int(script['updated_at'].timestamp())}:F>"

    text = script["script_text"]
    display_text = text if len(text) <= 1000 else text[:997] + "..."

    embed = create_embed(
        title=f"Script: {script['name']}",
        description=f"```\n{display_text}\n```",
    )
    embed.add_field(name="Faction", value=faction_data["display_name"], inline=True)
    embed.add_field(name="Runs On", value=runs_on, inline=True)
    embed.add_field(name="Run Count", value=str(script["run_count"]), inline=True)
    embed.add_field(name="Created", value=created, inline=True)
    embed.add_field(name="Updated", value=updated, inline=True)
    embed.add_field(name="Last Run", value=last_run, inline=True)

    await interaction.followup.send(embed=embed)
