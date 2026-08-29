# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int, get_faction_by_id
from services.pact_service import (
    get_pact,
    preview_intelligence_sharing_join,
    join_intelligence_sharing_pact,
    INTELLIGENCE_SHARING_PACT_TYPE,
)
from services.validation_service import require_faction


class ConfirmIntelligenceSharingJoinView(discord.ui.View):
    def __init__(self, pact_id: int, faction_id: int, faction_display_name: str, faction_color: int,
                 at_risk_faction_ids: list, new_cost_per_member: int, member_count: int):
        super().__init__(timeout=60)
        self.pact_id = pact_id
        self.faction_id = faction_id
        self.faction_display_name = faction_display_name
        self.faction_color = faction_color
        self.at_risk_faction_ids = at_risk_faction_ids
        self.new_cost_per_member = new_cost_per_member
        self.member_count = member_count

    @discord.ui.button(label="Confirm Join", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            result = await join_intelligence_sharing_pact(self.pact_id, self.faction_id, self.at_risk_faction_ids)
        except ValueError as e:
            await interaction.response.edit_message(embed=error_embed("Error", str(e)), view=None)
            return

        removed_names = []
        for removed_id in result['removed_faction_ids']:
            removed_faction = await get_faction_by_id(removed_id)
            if removed_faction:
                removed_names.append(removed_faction.display_name)

        description = (
            f"**{self.faction_display_name}** has joined the Intelligence Sharing pact.\n\n"
            f"**Total Members:** {result['member_count']}\n"
            f"**Cost per Member:** {self.new_cost_per_member} Influence"
        )
        if removed_names:
            description += f"\n\n**Removed (could not afford new cost):** {', '.join(removed_names)}"

        embed = success_embed(title="Joined Pact", description=description)
        embed.color = self.faction_color
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=error_embed("Join cancelled."), view=None)


@app_commands.command(name="join-intelligence-sharing", description="Join an Intelligence Sharing pact")
@app_commands.describe(faction="Faction name", pact_id="Pact ID to join")
@require_access_level(0)
async def join_intelligence_sharing(interaction: discord.Interaction, faction: str, pact_id: int):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data.id
    faction_color = hex_to_int(faction_data.color)

    pact_data = await get_pact(pact_id)
    if not pact_data:
        await interaction.followup.send(embed=error_embed("Error", "Pact not found."))
        return

    if pact_data.pact_type != INTELLIGENCE_SHARING_PACT_TYPE:
        await interaction.followup.send(embed=error_embed("Error", "This pact is not an Intelligence Sharing pact. Use /pact join instead."))
        return

    try:
        preview = await preview_intelligence_sharing_join(pact_id, faction_id)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    at_risk_faction_ids = preview['at_risk_faction_ids']
    new_cost_per_member = preview['new_cost_per_member']

    if not at_risk_faction_ids:
        try:
            result = await join_intelligence_sharing_pact(pact_id, faction_id, at_risk_faction_ids)
        except ValueError as e:
            await interaction.followup.send(embed=error_embed("Error", str(e)))
            return

        embed = success_embed(
            title="Joined Pact",
            description=f"**{faction_data.display_name}** has joined the Intelligence Sharing pact.\n\n"
                        f"**Total Members:** {result['member_count']}\n"
                        f"**Cost per Member:** {new_cost_per_member} Influence"
        )
        embed.color = faction_color
        await interaction.followup.send(embed=embed)
        return

    at_risk_names = []
    for at_risk_id in at_risk_faction_ids:
        at_risk_faction = await get_faction_by_id(at_risk_id)
        if at_risk_faction:
            at_risk_names.append(at_risk_faction.display_name)

    embed = discord.Embed(
        title="Confirm Pact Join",
        description=f"**{faction_data.display_name}** joining this pact raises the cost to {new_cost_per_member} Influence per member.\n\n"
                    f"The following member(s) would be pushed to negative influence income and will be REMOVED from the pact:\n"
                    f"{', '.join(at_risk_names)}\n\n"
                    f"Confirm to add **{faction_data.display_name}** and remove the affected member(s).",
        color=0xFF6600,
    )
    view = ConfirmIntelligenceSharingJoinView(
        pact_id, faction_id, faction_data.display_name, faction_color,
        at_risk_faction_ids, new_cost_per_member, len(at_risk_faction_ids)
    )
    await interaction.followup.send(embed=embed, view=view)


async def setup(bot):
    bot.tree.add_command(join_intelligence_sharing)
