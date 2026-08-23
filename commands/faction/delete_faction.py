# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.views import OwnerOnlyView
from services.faction_service import delete_faction as delete_faction_service
from services.validation_service import require_faction


class ConfirmDeleteView(OwnerOnlyView):
    def __init__(self, owner_id: int, faction_id: int, faction_name: str):
        super().__init__(owner_id=owner_id, timeout=30)
        self.faction_id = faction_id
        self.faction_name = faction_name

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.defer()
        try:
            await delete_faction_service(self.faction_id)

            embed = success_embed(title="Faction Deleted", description=f"**{self.faction_name}** has been permanently deleted.")
            embed.add_field(name="Deleted By", value=interaction.user.mention, inline=True)
            embed.add_field(name="Note", value="All related data has been removed.", inline=False)
            await interaction.edit_original_response(embed=embed, view=None)
            self.stop()

        except Exception as e:
            await interaction.edit_original_response(embed=error_embed("Error", f"Failed to delete faction: {e}"), view=None)
            self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        embed = discord.Embed(title="Cancelled", description="Faction deletion has been cancelled.", color=0x95a5a6)
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


@app_commands.command(name="delete", description="Delete a faction permanently (Admin)")
@app_commands.describe(faction="The Name or ID of the faction to delete")
@require_access_level(4)
async def delete_faction(interaction: discord.Interaction, faction: str):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    view = ConfirmDeleteView(interaction.user.id, faction_data.id, faction_data.display_name)
    embed = discord.Embed(
        title="⚠️ Confirm Faction Deletion",
        description=f"Are you sure you want to delete **{faction_data.display_name}**?",
        color=0xe74c3c
    )
    embed.add_field(name="Faction Name", value=faction_data.name, inline=True)
    embed.add_field(name="Leader", value=faction_data.leader, inline=True)
    embed.add_field(name="Warning", value="This action is **permanent** and cannot be undone!", inline=False)
    await interaction.followup.send(embed=embed, view=view)


async def setup(bot):
    pass
