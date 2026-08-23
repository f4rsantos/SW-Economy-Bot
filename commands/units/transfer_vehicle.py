# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import success_embed, error_embed
from utils.faction_utils import get_faction, hex_to_int
from utils.fleet_utils import get_vehicle_in_fleet
from services.fleet_service import transfer_vehicle
from services.validation_service import require_faction, require_unit, require_vehicle


class TransferSuccessView(discord.ui.View):
    def __init__(self, amount: int, vehicle_data: dict, from_unit: dict, to_unit: dict, from_name: str, to_name: str, user_id: int, faction_color: int):
        super().__init__(timeout=180)
        self.amount = amount
        self.vehicle_data = vehicle_data
        self.from_unit = from_unit
        self.to_unit = to_unit
        self.from_name = from_name
        self.to_name = to_name
        self.user_id = user_id
        self.faction_color = faction_color
        self.hidden = False

    async def create_detail_embed(self) -> discord.Embed:
        if self.hidden:
            return discord.Embed(title="Vehicles Transferred", description="[HIDDEN]", color=self.faction_color)
        
        embed = success_embed(
            "Vehicles Transferred",
            f"**{self.amount:,}x {self.vehicle_data['name']}**\n\n"
            f"From: **{self.from_name}** ({self.from_unit['world_name']})\n"
            f"To: **{self.to_name}** ({self.to_unit['world_name']})"
        )
        embed.color = self.faction_color
        return embed

    @discord.ui.button(label="Hide", style=discord.ButtonStyle.secondary, row=0)
    async def hide_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(embed=error_embed("Error", "This is not your confirmation."), ephemeral=True)
            return
        self.hidden = not self.hidden
        button.label = "Show" if self.hidden else "Hide"
        await interaction.response.edit_message(embed=await self.create_detail_embed(), view=self)


@app_commands.command(name="transfer", description="Transfer vehicles between units")
@app_commands.describe(
    faction="Faction name or ID that owns the source unit",
    from_unit_id="Source unit ID or name",
    to_unit_id="Destination unit ID or name",
    vehicle_id="Vehicle display ID or name",
    amount="Number of vehicles to transfer",
    target_faction="Target faction name (for inter-faction transfers)",
    vehicle_faction_origin="Faction that owns the vehicle design (if not the source faction)"
)
@require_access_level(0)
@ephemeral_capable('faction')
async def transfer_vehicle_cmd(
    interaction: discord.Interaction,
    faction: str,
    from_unit_id: str,
    to_unit_id: str,
    vehicle_id: str,
    amount: int,
    target_faction: str = None,
    vehicle_faction_origin: str = None
):
    await defer_response(interaction)

    if amount < 1:
        await interaction.followup.send(embed=error_embed("Error", "Amount must be at least 1."))
        return

    if from_unit_id == to_unit_id:
        await interaction.followup.send(embed=error_embed("Error", "Cannot transfer to the same unit."))
        return

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data.color)

    r_from_unit = await require_unit(from_unit_id, faction_data.id)
    if not r_from_unit.ok: return await interaction.followup.send(embed=error_embed("Error", r_from_unit.error))
    from_unit = r_from_unit.data

    if from_unit['status_name'].lower() == 'debris':
        await interaction.followup.send(embed=error_embed("Error", "Cannot transfer vehicles from debris units."))
        return

    origin_faction_id = None
    if vehicle_faction_origin:
        r_origin_faction = await require_faction(vehicle_faction_origin)
        if not r_origin_faction.ok: return await interaction.followup.send(embed=error_embed("Error", r_origin_faction.error))
        origin_faction_id = r_origin_faction.data.id

    vehicle_data = await get_vehicle_in_fleet(vehicle_id, from_unit['id'], origin_faction_id)
    if not vehicle_data:
        await interaction.followup.send(embed=error_embed("Error", f"Vehicle '{vehicle_id}' not found in source unit."))
        return

    if target_faction:
        r_target_faction_data = await require_faction(target_faction)
        if not r_target_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_target_faction_data.error))
        target_faction_data = r_target_faction_data.data
        dest_faction_id = target_faction_data.id
    else:
        dest_faction_id = faction_data.id

    r_to_unit = await require_unit(to_unit_id, dest_faction_id)
    if not r_to_unit.ok: return await interaction.followup.send(embed=error_embed("Error", r_to_unit.error))
    to_unit = r_to_unit.data

    if to_unit['status_name'].lower() == 'debris':
        await interaction.followup.send(embed=error_embed("Error", "Cannot transfer vehicles to debris units."))
        return

    if from_unit['position'] != to_unit['position']:
        await interaction.followup.send(embed=error_embed("Error", f"Both units must be on the same world. Source is on {from_unit['world_name']}, destination is on {to_unit['world_name']}."))
        return

    try:
        await transfer_vehicle(from_unit['id'], to_unit['id'], vehicle_data['id'], amount)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    from_name = from_unit['name'] or f"Unit #{from_unit['faction_fleet_number']}"
    to_name = to_unit['name'] or f"Unit #{to_unit['faction_fleet_number']}"

    view = TransferSuccessView(
        amount=amount,
        vehicle_data=vehicle_data,
        from_unit=from_unit,
        to_unit=to_unit,
        from_name=from_name,
        to_name=to_name,
        user_id=interaction.user.id,
        faction_color=faction_color
    )

    await interaction.followup.send(embed=await view.create_detail_embed(), view=view)


async def setup(bot):
    bot.tree.add_command(transfer_vehicle_cmd)