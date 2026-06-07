import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from services.scripting.script_service import get_script_by_name, deactivate_script
from ._helpers import resolve_faction_with_access


class ConfirmDeleteView(discord.ui.View):
    def __init__(self, faction: dict, script: dict):
        super().__init__(timeout=30)
        self.faction = faction
        self.script = script

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        success = await deactivate_script(self.script["id"], self.faction["id"])
        if success:
            await interaction.response.edit_message(
                embed=success_embed(
                    title="Script Deleted",
                    description=f"Script **{self.script['name']}** has been deactivated.",
                ),
                view=None,
            )
        else:
            await interaction.response.edit_message(
                embed=error_embed("Failed to delete script. It may have already been removed."),
                view=None,
            )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=error_embed("Deletion cancelled."),
            view=None,
        )


@app_commands.command(name="delete", description="Deactivate a faction script")
@app_commands.describe(faction="Faction name", name="Script name")
@require_access_level(0)
async def script_delete(interaction: discord.Interaction, faction: str, name: str):
    await interaction.response.defer()

    faction_data, err = await resolve_faction_with_access(interaction, faction)
    if err:
        await interaction.followup.send(embed=error_embed(err))
        return

    script = await get_script_by_name(faction_data["id"], name)
    if not script:
        await interaction.followup.send(
            embed=error_embed(f"No active script named '{name}'.")
        )
        return

    embed = discord.Embed(
        title="Confirm Script Deletion",
        description=f"Delete script **{script['name']}** for **{faction_data['display_name']}**?\nThis cannot be undone (execution history is preserved).",
        color=0xFF6600,
    )
    view = ConfirmDeleteView(faction=faction_data, script=script)
    await interaction.followup.send(embed=embed, view=view)
