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
    get_fleets_at_world, intercept_transfer, seize_transfer, release_transfer, destroy_transfer
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

    interception_world_id = transfer['from_world_id'] if transfer['from_world_name'] == interception_world_name else transfer['to_world_id']
    try:
        await intercept_transfer(transfer_id, fleet_id, interception_world_id)
    except ValueError as e:
        await interaction.edit_original_response(embed=error_embed("Error", str(e)), view=None)
        return

    resources = await get_transfer_resources(transfer_id)
    resource_str = ", ".join([f"{handle_return(r['amount'])} {r['name']}" for r in resources])

    escort_note = " This transfer has an escort fleet, so the outcome should be decided by the engagement result before seizing or destroying it." if transfer['escort_fleet_id'] else ""

    embed = discord.Embed(
        title="Transfer Intercepted!",
        description=f"**{faction_name}** has intercepted a transfer at **{interception_world_name}** using **{fleet_name}**!\n\n"
                    f"**From:** {transfer['from_faction_name']} ({transfer['from_world_name']})\n"
                    f"**To:** {transfer['to_faction_name']} ({transfer['to_world_name']})\n"
                    f"**Resources:** {resource_str}\n\n"
                    f"Use `/interception seize {transfer_id}` to seize the resources, `/interception destroy {transfer_id}` to destroy them, "
                    f"or `/interception release {transfer_id}` to let it through.{escort_note}",
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


class ConfirmEngagementView(OwnerOnlyView):
    def __init__(self, owner_id: int, action: str, transfer_id: int, faction_data: dict):
        super().__init__(owner_id=owner_id, timeout=60)
        self.action = action
        self.transfer_id = transfer_id
        self.faction_data = faction_data

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.defer()
        if self.action == 'seize':
            await _do_seize(interaction, self.transfer_id, self.faction_data)
        else:
            await _do_destroy(interaction, self.transfer_id, self.faction_data)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.edit_message(embed=error_embed("Cancelled", "No action was taken."), view=None)
        self.stop()


async def _do_seize(interaction, transfer_id: int, faction_data: dict):
    faction_color = hex_to_int(faction_data['color'])

    transfer = await get_intercepted_transfer(transfer_id, faction_data['id'])
    if not transfer:
        await interaction.edit_original_response(embed=error_embed("Error", "Transfer not found, not intercepted, or you are not the intercepting faction."), view=None)
        return

    resources = await get_transfer_resources(transfer_id)

    try:
        await seize_transfer(transfer_id, faction_data['id'], transfer['interception_world_id'])
    except ValueError as e:
        await interaction.edit_original_response(embed=error_embed("Error", str(e)), view=None)
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
    await interaction.edit_original_response(embed=embed, view=None)


async def _do_destroy(interaction, transfer_id: int, faction_data: dict):
    faction_color = hex_to_int(faction_data['color'])

    transfer = await get_intercepted_transfer(transfer_id, faction_data['id'])
    if not transfer:
        await interaction.edit_original_response(embed=error_embed("Error", "Transfer not found, not intercepted, or you are not the intercepting faction."), view=None)
        return

    resources = await get_transfer_resources(transfer_id)
    resource_str = ", ".join([f"{handle_return(r['amount'])} {r['name']}" for r in resources])

    try:
        await destroy_transfer(transfer_id)
    except ValueError as e:
        await interaction.edit_original_response(embed=error_embed("Error", str(e)), view=None)
        return

    try:
        leader_role_id = await get_faction_leader_role_id(transfer['from_faction_id'])
        if leader_role_id:
            role = interaction.guild.get_role(leader_role_id)
            if role:
                await interaction.channel.send(
                    f"{role.mention}",
                    embed=error_embed("Transfer Destroyed!", f"Your transfer (#{transfer_id}) of {resource_str} has been destroyed by **{faction_data['display_name']}**!")
                )
    except Exception:
        pass

    embed = success_embed(
        title="Resources Destroyed",
        description=f"**{faction_data['display_name']}** has destroyed {resource_str} from transfer #{transfer_id}."
    )
    embed.color = faction_color
    await interaction.edit_original_response(embed=embed, view=None)


async def _confirm_engagement(interaction: discord.Interaction, action: str, transfer_id: int, faction_data: dict, transfer: dict):
    faction_color = hex_to_int(faction_data['color'])
    verb = "seize" if action == 'seize' else "destroy"
    embed = discord.Embed(
        title=f"Confirm {verb.title()}",
        description=f"Are you sure you want to {verb} transfer #{transfer_id}?\n\n"
                    f"This transfer has an escort fleet. Only {verb} it once the engagement result against the escort has been determined.",
        color=faction_color
    )
    embed.set_footer(text="You have 60 seconds to confirm.")
    view = ConfirmEngagementView(interaction.user.id, action, transfer_id, faction_data)
    await interaction.followup.send(embed=embed, view=view)


class InterceptionGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="interception", description="Intercept, seize, release, or destroy resource transfers")

    @app_commands.command(name="start", description="Intercept an in-transit resource transfer")
    @app_commands.describe(
        transfer_id="ID of the transfer to intercept",
        faction="Your faction name"
    )
    @require_access_level(0)
    async def start(
        self,
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
        self,
        interaction: discord.Interaction,
        transfer_id: int,
        faction: str
    ):
        await interaction.response.defer()

        r_faction_data = await require_faction(faction)
        if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
        faction_data = r_faction_data.data

        transfer = await get_intercepted_transfer(transfer_id, faction_data['id'])
        if not transfer:
            await interaction.followup.send(embed=error_embed("Error", "Transfer not found, not intercepted, or you are not the intercepting faction."))
            return

        if transfer['escort_fleet_id']:
            await _confirm_engagement(interaction, 'seize', transfer_id, faction_data, transfer)
            return

        await _do_seize(interaction, transfer_id, faction_data)

    @app_commands.command(name="destroy", description="Destroy the resources of an intercepted transfer")
    @app_commands.describe(
        transfer_id="ID of the intercepted transfer to destroy",
        faction="Your faction name"
    )
    @require_access_level(0)
    async def destroy(
        self,
        interaction: discord.Interaction,
        transfer_id: int,
        faction: str
    ):
        await interaction.response.defer()

        r_faction_data = await require_faction(faction)
        if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
        faction_data = r_faction_data.data

        transfer = await get_intercepted_transfer(transfer_id, faction_data['id'])
        if not transfer:
            await interaction.followup.send(embed=error_embed("Error", "Transfer not found, not intercepted, or you are not the intercepting faction."))
            return

        if transfer['escort_fleet_id']:
            await _confirm_engagement(interaction, 'destroy', transfer_id, faction_data, transfer)
            return

        await _do_destroy(interaction, transfer_id, faction_data)

    @app_commands.command(name="release", description="Release an intercepted transfer to continue")
    @app_commands.describe(
        transfer_id="ID of the intercepted transfer to release",
        faction="Your faction name"
    )
    @require_access_level(0)
    async def release(
        self,
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
    bot.tree.add_command(InterceptionGroup())
