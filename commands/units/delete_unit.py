# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from discord.ui import View, Button
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import success_embed, error_embed
from utils.faction_utils import get_faction_by_leader, hex_to_int
from services.user_service import get_user_access_level
from services.fleet_service import delete_fleet, get_fleet_vehicle_count
from services.validation_service import require_faction, require_unit
from utils.autocomplete import faction_autocomplete


class ConfirmDeleteView(View):
    def __init__(self, unit_id: int, faction_id: int, unit_name: str, vehicle_count: int):
        super().__init__(timeout=60)
        self.unit_id = unit_id
        self.faction_id = faction_id
        self.unit_name = unit_name
        self.vehicle_count = vehicle_count

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _: Button):
        faction_check = await get_faction_by_leader(interaction.user.id)
        user_level = await get_user_access_level(interaction.user.id)
        is_leader = faction_check and faction_check.id == self.faction_id

        if not (is_leader or user_level >= 1):
            await interaction.response.send_message(embed=error_embed("Error", "You must be the faction leader or an admin to delete this unit."))
            return

        await delete_fleet(self.unit_id)

        embed = success_embed("Unit Deleted", f"Unit **{self.unit_name}** has been permanently deleted.")
        if self.vehicle_count > 0:
            embed.add_field(name="Vehicles Destroyed", value=f"{self.vehicle_count} vehicle(s) were destroyed with the unit.", inline=False)

        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: Button):
        await interaction.response.edit_message(embed=error_embed("Deletion Cancelled", f"Unit **{self.unit_name}** was not deleted."), view=None)
        self.stop()


@app_commands.command(name="delete", description="Permanently delete a unit")
@app_commands.describe(
    faction="Faction owning the unit",
    unit_id="ID or name of the unit to delete"
)
@require_access_level(0)
@ephemeral_capable('faction')
async def unit_delete(
    interaction: discord.Interaction,
    faction: str,
    unit_id: str
):
    await defer_response(interaction)

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    user_level = await get_user_access_level(interaction.user.id)
    is_leader = faction_data.leader_id == interaction.user.id
    if not (is_leader or user_level >= 1):
        await interaction.followup.send(embed=error_embed("Error", "You must be the faction leader or an admin to delete units."))
        return

    faction_color = hex_to_int(faction_data.color)

    r_unit = await require_unit(unit_id, faction_data.id)
    if not r_unit.ok: return await interaction.followup.send(embed=error_embed("Error", r_unit.error))
    unit = r_unit.data

    vehicle_count = await get_fleet_vehicle_count(unit['id'])

    unit_name = unit['name'] or f"Unit #{unit['faction_fleet_number']}"

    embed = discord.Embed(
        title="⚠️ Confirm Unit Deletion",
        description=f"Are you sure you want to permanently delete **{unit_name}**?",
        color=faction_color
    )
    embed.add_field(name="Faction",  value=faction_data.display_name, inline=True)
    embed.add_field(name="Location", value=unit['world_name'],           inline=True)
    embed.add_field(name="Status",   value=unit['status_name'],          inline=True)
    embed.add_field(name="Health",   value=f"{unit['health']}%",         inline=True)

    if vehicle_count > 0:
        embed.add_field(name="⚠️ WARNING", value=f"This unit contains **{vehicle_count} vehicle(s)** that will be **DESTROYED**!", inline=False)
        embed.color = discord.Color.red()

    embed.set_footer(text="This action cannot be undone. You have 60 seconds to confirm.")

    view = ConfirmDeleteView(unit['id'], faction_data.id, unit_name, vehicle_count)
    await interaction.followup.send(embed=embed, view=view)


async def setup(bot):
    unit_delete.autocomplete('faction')(faction_autocomplete)
    bot.tree.add_command(unit_delete)
