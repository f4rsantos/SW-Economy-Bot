import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed, create_embed
from services.scripting.script_service import get_active_scripts
from utils.scripting_helpers import resolve_faction_with_access


@app_commands.command(name="list", description="List active scripts for a faction")
@app_commands.describe(faction="Faction name")
@require_access_level(0)
async def script_list(interaction: discord.Interaction, faction: str):
    await interaction.response.defer()

    faction_data, err = await resolve_faction_with_access(interaction, faction)
    if err:
        await interaction.followup.send(embed=error_embed(err))
        return

    scripts = await get_active_scripts(faction_data["id"])
    if not scripts:
        await interaction.followup.send(
            embed=create_embed(
                title=f"Scripts: {faction_data['display_name']}",
                description="No active scripts.",
            ),
        )
        return

    lines = []
    for s in scripts:
        runs_on = s["trigger_day"] or "Income Day"
        last = f"<t:{int(s['last_run_at'].timestamp())}:R>" if s["last_run_at"] else "never"
        lines.append(f"**{s['name']}** (ID {s['id']}) — runs on {runs_on} — last run {last} — {s['run_count']} run(s)")

    embed = create_embed(
        title=f"Scripts: {faction_data['display_name']}",
        description="\n".join(lines),
    )
    await interaction.followup.send(embed=embed)
