# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.views import OwnerOnlyView
from database.cache_manager import cache_manager
from services.faction_service import list_factions as list_factions_service, NO_LEADER_LABEL, NO_TREATMENT_LABEL

FACTIONS_PER_PAGE = 10


class FactionPageJumpModal(discord.ui.Modal, title="Jump to Page"):
    page_number = discord.ui.TextInput(label="Page Number", placeholder="Enter page number...", required=True, max_length=5)

    def __init__(self, faction_view):
        super().__init__()
        self.faction_view = faction_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            page = int(self.page_number.value) - 1
            if page < 0 or page >= self.faction_view.total_pages:
                page = 0
            self.faction_view.page = page
            await interaction.response.edit_message(embed=self.faction_view.get_embed(), view=self.faction_view)
        except ValueError:
            await interaction.response.send_message(embed=error_embed("Error", "Please enter a valid page number."))


class FactionPaginationView(OwnerOnlyView):
    def __init__(self, owner_id: int, factions: list, long_sort: bool, page: int = 0):
        super().__init__(owner_id=owner_id, timeout=180)
        self.factions = factions
        self.long_sort = long_sort
        self.page = page
        self.total_pages = (len(factions) - 1) // FACTIONS_PER_PAGE + 1

    def get_embed(self) -> discord.Embed:
        start_idx = self.page * FACTIONS_PER_PAGE
        page_factions = self.factions[start_idx:start_idx + FACTIONS_PER_PAGE]
        title = f"Factions ({'by Name Length' if self.long_sort else 'Alphabetical'}) - Total: {len(self.factions)}"
        embed = discord.Embed(title=title, description=f"Page {self.page + 1}/{self.total_pages}", color=0x3498db)

        for faction in page_factions:
            type_label = {0: "[Nation]", 1: "[Company]", 2: "[Pirate]"}.get(faction.faction_type, "[Nation]")
            if self.long_sort:
                display_name = faction.display_name
                field_name = f"{type_label} {display_name} ({len(display_name)} chars)"
            else:
                formal = f" ({faction.formal_name})" if faction.formal_name != faction.name else ""
                field_name = f"{type_label} {faction.name}{formal}"
            if faction.leader_id is None:
                leader_display = NO_LEADER_LABEL
            else:
                leader_user = cache_manager.get_user(faction.leader_id)
                leader_display = (leader_user.treatment if leader_user else None) or NO_TREATMENT_LABEL
            embed.add_field(name=field_name, value=f"ID: `{faction.id}` | Leader: {leader_display}", inline=False)

        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary, row=0)
    async def prev_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page = (self.page - 1) % self.total_pages
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Jump to Page", style=discord.ButtonStyle.primary, row=0)
    async def jump_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(FactionPageJumpModal(self))

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, row=0)
    async def next_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page = (self.page + 1) % self.total_pages
        await interaction.response.edit_message(embed=self.get_embed(), view=self)


@app_commands.command(name="list", description="List all factions")
@app_commands.describe(long="Show factions sorted by formal name length instead of alphabetically")
@require_access_level(0)
async def list_factions(interaction: discord.Interaction, long: bool = False):
    await interaction.response.defer()
    factions = await list_factions_service(long)

    if not factions:
        await interaction.followup.send(embed=success_embed(title="Factions", description="No factions exist yet."))
        return

    view = FactionPaginationView(interaction.user.id, list(factions), long)
    await interaction.followup.send(embed=view.get_embed(), view=view)


async def setup(bot):
    pass
