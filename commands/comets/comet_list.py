import discord
from discord import app_commands
from discord.ui import View, Select
from utils.checks import require_access_level
from utils.embeds import error_embed
from services.comet_service import get_comets, get_comet

COMETS_PER_PAGE = 10


class CometDetailView(View):
    def __init__(self, comet: dict, user_id: int, all_comets: list, page: int):
        super().__init__(timeout=180)
        self.comet = comet
        self.user_id = user_id
        self.all_comets = all_comets
        self.page = page

    def create_detail_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=self.comet['name'],
            description=self.comet['message'],
            color=0x2B2D31
        )
        embed.add_field(name="Discoverer", value=f"<@{self.comet['discoverer']}>", inline=True)
        return embed

    @discord.ui.button(label="Back to List", style=discord.ButtonStyle.secondary, row=0)
    async def back_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=error_embed("Error", "This is not your comet list.")
            )
            return
        view = CometListView(self.all_comets, self.user_id, self.page)
        await interaction.response.edit_message(embed=view.create_list_embed(), view=view)


class CometListView(View):
    def __init__(self, comets: list, user_id: int, page: int = 0):
        super().__init__(timeout=180)
        self.comets = comets
        self.user_id = user_id
        self.page = page
        self.total_pages = max(1, (len(comets) - 1) // COMETS_PER_PAGE + 1)
        self.comet_select = None
        self.add_comet_selector()

    def add_comet_selector(self):
        if self.comet_select:
            self.remove_item(self.comet_select)
        start = self.page * COMETS_PER_PAGE
        page_comets = self.comets[start:start + COMETS_PER_PAGE]
        options = [
            discord.SelectOption(
                label=c['name'][:100],
                value=str(c['id'])
            )
            for c in page_comets
        ]
        self.comet_select = Select(
            placeholder="Select a comet to view...",
            options=options,
            row=0
        )
        self.comet_select.callback = self.comet_selected
        self.add_item(self.comet_select)

    async def comet_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=error_embed("Error", "This is not your comet list.")
            )
            return
        comet_id = int(self.comet_select.values[0])
        comet = await get_comet(comet_id)
        if not comet:
            await interaction.response.send_message(
                embed=error_embed("Error", "Comet not found.")
            )
            return
        detail_view = CometDetailView(comet, self.user_id, self.comets, self.page)
        await interaction.response.edit_message(
            embed=detail_view.create_detail_embed(), view=detail_view
        )

    def create_list_embed(self) -> discord.Embed:
        start = self.page * COMETS_PER_PAGE
        page_comets = self.comets[start:start + COMETS_PER_PAGE]
        embed = discord.Embed(
            title="Comets",
            description=f"Page {self.page + 1}/{self.total_pages} — {len(self.comets)} recorded",
            color=0x2B2D31
        )
        for c in page_comets:
            embed.add_field(
                name=c['name'],
                value=f"Discoverer: <@{c['discoverer']}>",
                inline=False
            )
        embed.set_footer(text="Select a comet from the dropdown to view details")
        return embed

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, row=1)
    async def prev_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=error_embed("Error", "This is not your comet list.")
            )
            return
        self.page = (self.page - 1) % self.total_pages
        self.add_comet_selector()
        await interaction.response.edit_message(embed=self.create_list_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, row=1)
    async def next_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=error_embed("Error", "This is not your comet list.")
            )
            return
        self.page = (self.page + 1) % self.total_pages
        self.add_comet_selector()
        await interaction.response.edit_message(embed=self.create_list_embed(), view=self)


@app_commands.command(name="list", description="Browse all discovered comets")
@require_access_level(0)
async def comet_list(interaction: discord.Interaction):
    comets = await get_comets(limit=200)
    if not comets:
        await interaction.response.send_message(
            embed=error_embed("No Comets", "No comets have been discovered yet.")
        )
        return
    view = CometListView(comets, interaction.user.id)
    await interaction.response.send_message(embed=view.create_list_embed(), view=view)


async def setup(bot):
    pass
