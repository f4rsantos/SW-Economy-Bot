import discord
from discord import app_commands
from datetime import datetime, timezone, timedelta
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return
from utils.faction_utils import hex_to_int
from utils.views import OwnerOnlyView
from services.faction_service import get_faction_leader_role_id
from services.validation_service import require_faction
from services.transfer_service import (
    get_transfer, get_intercepted_transfer, get_transfer_resources,
    get_fleets_at_world, intercept_transfer, seize_transfer, release_transfer
)


class InterceptFleetView(OwnerOnlyView):
    def __init__(self, owner_id, fleets, transfer_id, faction_id, faction_color, faction_name, interception_world_name, interception_world_id):
        super().__init__(owner_id=owner_id, timeout=60)
        self.transfer_id = transfer_id
        self.faction_id = faction_id
        self.faction_color = faction_color
        self.faction_name = faction_name
        self.interception_world_name = interception_world_name
        self.interception_world_id = interception_world_id
        self.fleets = fleets
        options = []
        for fleet in fleets:
            fleet_name = fleet['name'] if fleet['name'] else f"Fleet #{fleet['faction_fleet_number']}"
            options.append(discord.SelectOption(
                label=fleet_name[:100],
                value=str(fleet['id']),
                description=f"Status: {fleet['status']}"
            ))
        self.add_item(InterceptFleetSelect(options))


class InterceptFleetSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Select fleet to intercept with...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        view: InterceptFleetView = self.view
        fleet_id = int(self.values[0])
        fleet_name = next((o.label for o in self.options if o.value == str(fleet_id)), "Unknown Fleet")
        await _execute_interception(interaction, view.transfer_id, view.faction_color,
                                    view.faction_name, view.interception_world_name,
                                    fleet_id, fleet_name)


async def _execute_interception(interaction, transfer_id, faction_color, faction_name,
                                 interception_world_name, fleet_id, fleet_name):
    if not interaction.response.is_done():
        await interaction.response.defer()

    transfer = await get_transfer(transfer_id, status='in_transit')
    if not transfer:
        await interaction.edit_original_response(
            embed=error_embed("Error", "Transfer no longer valid or already intercepted."), view=None
        )
        return

    try:
        await intercept_transfer(transfer_id, fleet_id)
    except ValueError as e:
        await interaction.edit_original_response(embed=error_embed("Error", str(e)), view=None)
        return

    resources = await get_transfer_resources(transfer_id)
    resource_str = ", ".join([f"{handle_return(r['amount'])} {r['name']}" for r in resources])

    embed = discord.Embed(
        title="Transfer Intercepted!",
        description=f"**{faction_name}** has intercepted a transfer at **{interception_world_name}** using **{fleet_name}**!\n\n"
                    f"**From:** {transfer['from_faction_name']} ({transfer['from_world_name']})\n"
                    f"**To:** {transfer['to_faction_name']} ({transfer['to_world_name']})\n"
                    f"**Resources:** {resource_str}\n\n"
                    f"Use `/seize {transfer_id}` to seize the resources or `/release {transfer_id}` to let it through.",
        color=faction_color
    )
    await interaction.edit_original_response(embed=embed, view=None)

    try:
        leader_role_id = await get_faction_leader_role_id(transfer['from_faction_id'])
        if leader_role_id:
            role = interaction.guild.get_role(leader_role_id)
            if role:
                await interaction.channel.send(
                    f"{role.mention}",
                    embed=error_embed("Transfer Intercepted!", f"Your transfer (#{transfer_id}) of {resource_str} has been intercepted by **{faction_name}** at **{interception_world_name}**!")
                )
    except Exception:
        pass


@app_commands.command(name="intercept", description="Intercept an in-transit resource transfer")
@app_commands.describe(
    transfer_id="ID of the transfer to intercept",
    faction="Your faction name"
)
@require_access_level(0)
async def intercept(
    interaction: discord.Interaction,
    transfer_id: int,
    faction: str
):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    intercepting_faction_id = faction_data['id']
    faction_color = hex_to_int(faction_data['color'])

    transfer = await get_transfer(transfer_id, status='in_transit')
    if not transfer:
        await interaction.followup.send(embed=error_embed("Error", "Transfer not found or not in transit."))
        return

    current_time = datetime.now(timezone.utc)
    start_time = transfer['start_time']
    arrival_time = transfer['arrival_time']
    total_duration = (arrival_time - start_time).total_seconds()
    elapsed = (current_time - start_time).total_seconds()
    progress = elapsed / total_duration if total_duration > 0 else 1

    if progress < 0.5:
        interception_world_id = transfer['from_world_id']
        interception_world_name = transfer['from_world_name']
    else:
        interception_world_id = transfer['to_world_id']
        interception_world_name = transfer['to_world_name']

    fleets = await get_fleets_at_world(intercepting_faction_id, interception_world_id)
    if not fleets:
        await interaction.followup.send(
            embed=error_embed("Error", f"You need a fleet at **{interception_world_name}** to intercept this transfer.")
        )
        return

    if len(fleets) == 1:
        fleet = fleets[0]
        fleet_name = fleet['name'] if fleet['name'] else f"Fleet #{fleet['faction_fleet_number']}"
        await _execute_interception(interaction, transfer_id, faction_color,
                                    faction_data['display_name'], interception_world_name,
                                    fleet['id'], fleet_name)
    else:
        view = InterceptFleetView(
            interaction.user.id, list(fleets), transfer_id,
            intercepting_faction_id, faction_color, faction_data['display_name'],
            interception_world_name, interception_world_id
        )
        await interaction.followup.send(
            embed=success_embed("Select Intercepting Fleet", f"Multiple fleets at **{interception_world_name}**. Select which fleet will intercept."),
            view=view
        )


@app_commands.command(name="seize", description="Seize an intercepted resource transfer")
@app_commands.describe(
    transfer_id="ID of the intercepted transfer to seize",
    faction="Your faction name"
)
@require_access_level(0)
async def seize(
    interaction: discord.Interaction,
    transfer_id: int,
    faction: str
):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data['color'])

    transfer = await get_intercepted_transfer(transfer_id, faction_data['id'])
    if not transfer:
        await interaction.followup.send(embed=error_embed("Error", "Transfer not found, not intercepted, or you are not the intercepting faction."))
        return

    resources = await get_transfer_resources(transfer_id)

    try:
        await seize_transfer(transfer_id, faction_data['id'], transfer['interception_world_id'])
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    resource_str = ", ".join([f"{handle_return(r['amount'])} {r['name']}" for r in resources])

    try:
        leader_role_id = await get_faction_leader_role_id(transfer['from_faction_id'])
        if leader_role_id:
            role = interaction.guild.get_role(leader_role_id)
            if role:
                await interaction.channel.send(
                    f"{role.mention}",
                    embed=error_embed("Transfer Seized!", f"Your transfer (#{transfer_id}) of {resource_str} has been seized by **{faction_data['display_name']}**!")
                )
    except Exception:
        pass

    embed = success_embed(
        title="Resources Seized",
        description=f"**{faction_data['display_name']}** has seized {resource_str} from transfer #{transfer_id}."
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


@app_commands.command(name="release", description="Release an intercepted transfer to continue")
@app_commands.describe(
    transfer_id="ID of the intercepted transfer to release",
    faction="Your faction name"
)
@require_access_level(0)
async def release(
    interaction: discord.Interaction,
    transfer_id: int,
    faction: str
):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data['color'])

    transfer = await get_intercepted_transfer(transfer_id, faction_data['id'])
    if not transfer:
        await interaction.followup.send(embed=error_embed("Error", "Transfer not found, not intercepted, or you are not the intercepting faction."))
        return

    new_arrival = datetime.now(timezone.utc) + timedelta(hours=1)

    try:
        await release_transfer(transfer_id, new_arrival)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    try:
        leader_role_id = await get_faction_leader_role_id(transfer['from_faction_id'])
        if leader_role_id:
            role = interaction.guild.get_role(leader_role_id)
            if role:
                await interaction.channel.send(
                    f"{role.mention}",
                    embed=success_embed("Transfer Released", f"**{faction_data['display_name']}** has released your transfer (#{transfer_id}) to **{transfer['to_faction_name']}**.")
                )
    except Exception:
        pass

    embed = success_embed(
        title="Transfer Released",
        description=f"**{faction_data['display_name']}** has released transfer #{transfer_id} to continue to **{transfer['to_faction_name']}**."
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(intercept)
    bot.tree.add_command(seize)
    bot.tree.add_command(release)
