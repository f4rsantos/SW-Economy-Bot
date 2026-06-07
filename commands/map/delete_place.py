import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.views import OwnerOnlyView
from services.map_service import get_world_asset_counts, delete_world
from services.validation_service import require_world


class ConfirmDeleteWorldView(OwnerOnlyView):
    def __init__(self, owner_id: int, world_id: int, world_name: str, asset_counts: dict):
        super().__init__(owner_id=owner_id, timeout=30)
        self.world_id = world_id
        self.world_name = world_name
        self.asset_counts = asset_counts

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        try:
            await delete_world(self.world_id, self.world_name)

            embed = success_embed(title="World Deleted", description=f"**{self.world_name}** has been removed from the map.")
            embed.add_field(name="Deleted By", value=interaction.user.mention, inline=True)
            cleanup = []
            if self.asset_counts.get('fleets', 0) > 0:
                cleanup.append(f"• Deleted {self.asset_counts['fleets']} fleets")
            if self.asset_counts.get('territory', 0) > 0:
                cleanup.append(f"• Removed territory from {self.asset_counts['territory']} factions")
            if self.asset_counts.get('buildings', 0) > 0:
                cleanup.append(f"• Demolished {self.asset_counts['buildings']} buildings")
            if cleanup:
                embed.add_field(name="Cleanup Report", value="\n".join(cleanup), inline=False)
            await interaction.response.edit_message(embed=embed, view=None)
            self.stop()
        except Exception as e:
            await interaction.response.edit_message(embed=error_embed("Error", f"Failed to delete world: {e}"), view=None)
            self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        embed = discord.Embed(title="Cancelled", description=f"Deletion of **{self.world_name}** cancelled.", color=0x95a5a6)
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


@app_commands.command(name="delete-place", description="Delete a world (Admin)")
@app_commands.describe(world="World name to delete")
@require_access_level(7)
async def delete_place(interaction: discord.Interaction, world: str):
    await interaction.response.defer()

    r_world = await require_world(world)
    if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
    world_data = r_world.data

    world_id = world_data['id']
    try:
        asset_counts = await get_world_asset_counts(world_id)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    view = ConfirmDeleteWorldView(interaction.user.id, world_id, world_data['name'], asset_counts)
    embed = discord.Embed(title="⚠️ Confirm World Deletion", description=f"Are you sure you want to delete **{world_data['name']}**?", color=0xe74c3c)

    conn_msg = []
    if asset_counts['fleets'] > 0:
        conn_msg.append(f"**{asset_counts['fleets']}** Fleets stationed")
    if asset_counts['territory'] > 0:
        conn_msg.append(f"**{asset_counts['territory']}** Factions present")
    if asset_counts['buildings'] > 0:
        conn_msg.append(f"**{asset_counts['buildings']}** Buildings constructed")

    if conn_msg:
        embed.add_field(name="Detected Assets", value="\n".join(conn_msg), inline=False)
        embed.add_field(name="WARNING", value="Confirming will **permanently destroy** all these assets!", inline=False)
    else:
        embed.add_field(name="Status", value="No active assets detected.", inline=False)

    await interaction.followup.send(embed=embed, view=view)


async def setup(bot):
    bot.tree.add_command(delete_place)
