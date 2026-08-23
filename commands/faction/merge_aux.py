# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import get_faction
from services.validation_service import require_faction
from utils.views import OwnerOnlyView
from services.faction_service import merge_aux as merge_aux_service, get_faction_territory_summary


class ConfirmMergeView(OwnerOnlyView):
    def __init__(self, owner_id: int, from_faction_id: int, from_faction_name: str, to_faction_id: int, to_faction_name: str):
        super().__init__(owner_id=owner_id, timeout=60)
        self.from_faction_id = from_faction_id
        self.from_faction_name = from_faction_name
        self.to_faction_id = to_faction_id
        self.to_faction_name = to_faction_name

    @discord.ui.button(label="Confirm Merge", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.defer()
        try:
            result = await merge_aux_service(self.from_faction_id, self.to_faction_id)

            embed = success_embed(
                title="Faction Merged",
                description=f"**{self.from_faction_name}** has been merged into **{self.to_faction_name}**"
            )
            embed.add_field(name="Territories Transferred", value=str(result['territories_transferred']), inline=True)
            embed.add_field(name="Executed By", value=interaction.user.mention, inline=True)
            embed.add_field(name="Note", value="Only territories were transferred. Buildings, fleets, vehicles, and treasury were NOT transferred.", inline=False)
            await interaction.edit_original_response(embed=embed, view=None)
            self.stop()

        except Exception as e:
            await interaction.edit_original_response(embed=error_embed("Error", f"Failed to merge factions: {e}"), view=None)
            self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        embed = discord.Embed(title="Cancelled", description="Faction merge has been cancelled.", color=0x95a5a6)
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


@app_commands.command(name="merge", description="Merge auxiliary faction into another faction (Admin)")
@app_commands.describe(
    from_faction="Name or ID of the faction to merge (will be deleted)",
    to_faction="Name or ID of the faction to receive territories"
)
@require_access_level(9)
async def merge_aux(interaction: discord.Interaction, from_faction: str, to_faction: str):
    r_from_faction_data, r_to_faction_data = await asyncio.gather(
        require_faction(from_faction),
        require_faction(to_faction)
    )
    if not r_from_faction_data.ok:
        await interaction.response.send_message(embed=error_embed("Error", r_from_faction_data.error))
        return
    from_faction_data = r_from_faction_data.data
    if not r_to_faction_data.ok:
        await interaction.response.send_message(embed=error_embed("Error", r_to_faction_data.error))
        return
    to_faction_data = r_to_faction_data.data

    if from_faction_data.id == to_faction_data.id:
        await interaction.response.send_message(embed=error_embed("Error", "Cannot merge a faction into itself."))
        return

    territory_info = await get_faction_territory_summary(from_faction_data.id)

    embed = discord.Embed(
        title="⚠️ Confirm Faction Merge",
        description=f"You are about to merge **{from_faction_data.display_name}** into **{to_faction_data.display_name}**",
        color=0xe74c3c
    )
    embed.add_field(name="Source Faction", value=from_faction_data.display_name, inline=True)
    embed.add_field(name="Target Faction", value=to_faction_data.display_name, inline=True)
    embed.add_field(name="Worlds with Territory", value=str(territory_info['world_count']), inline=True)
    embed.add_field(name="Total Territory", value=str(territory_info['total_territory']), inline=True)
    embed.add_field(
        name="Warning",
        value=(
            f"• **{from_faction_data.display_name}** will be PERMANENTLY DELETED\n"
            f"• All territories transferred to **{to_faction_data.display_name}**\n"
            f"• This action CANNOT be undone"
        ),
        inline=False
    )

    view = ConfirmMergeView(
        interaction.user.id,
        from_faction_data.id, from_faction_data.display_name,
        to_faction_data.id, to_faction_data.display_name
    )
    await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    pass
