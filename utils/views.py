import discord
from datetime import timezone
from typing import Optional
from utils.embeds import success_embed, error_embed

PAGE_SIZE = 10


class RecruitmentPaginatorView(discord.ui.View):
    def __init__(self, owner_id: int, title: str, color: int, recruitments: list, total: int):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.title = title
        self.color = color
        self.recruitments = recruitments
        self.total = total
        self.page = 0
        self.max_page = max(0, (len(recruitments) - 1) // PAGE_SIZE)
        self._update_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                embed=error_embed("Not Allowed", "You cannot interact with someone else's command."),
                ephemeral=True,
            )
            return False
        return True

    def _update_buttons(self):
        self.prev_button.disabled = self.page == 0
        self.next_button.disabled = self.page == self.max_page

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title=self.title, color=self.color, timestamp=discord.utils.utcnow())
        start = self.page * PAGE_SIZE
        page_items = self.recruitments[start: start + PAGE_SIZE]

        for recruit in page_items:
            completion_time = recruit['completion_time']
            if completion_time.tzinfo is None:
                completion_time = completion_time.replace(tzinfo=timezone.utc)
            secs = int((completion_time - discord.utils.utcnow()).total_seconds())
            status = "**Ready** (pending sync)" if secs <= 0 else "In Training"
            embed.add_field(
                name=f"[#{recruit['id']}] {recruit['amount']:,} {recruit['role_name']}",
                value=f"**Status:** {status}\n**Ready:** <t:{int(completion_time.timestamp())}:R>",
                inline=False,
            )

        footer = f"Total in training: {self.total:,}"
        if self.max_page > 0:
            footer += f" | Page {self.page + 1}/{self.max_page + 1}"
        embed.set_footer(text=footer)
        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


class OwnerOnlyView(discord.ui.View):
    def __init__(self, owner_id: int, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                embed=error_embed("Not Allowed", "You cannot interact with someone else's command."),
                ephemeral=True
            )
            return False
        return True


class RegisterVehicleView(OwnerOnlyView):
    def __init__(self, owner_id: int, faction_id: int, faction_name: str, vehicle_name: str,
                 designation: Optional[str], vehicle_type: str, costs: dict, vehicle_data: dict = None):
        super().__init__(owner_id=owner_id, timeout=60)
        self.faction_id = faction_id
        self.faction_name = faction_name
        self.vehicle_name = vehicle_name
        self.designation = designation
        self.vehicle_type = vehicle_type
        self.costs = costs
        self.vehicle_data = vehicle_data

    @discord.ui.button(label="Register Vehicle", style=discord.ButtonStyle.green)
    async def register_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        from services.vehicle_service import register_vehicle, check_vehicle_exists, update_vehicle
        await interaction.response.defer()
        try:
            existing = await check_vehicle_exists(self.faction_id, self.vehicle_name)
            if existing:
                await update_vehicle(existing['id'], self.designation, self.costs, self.vehicle_data)
                title, label = f"{self.vehicle_type.title()} Replaced", "Replaced"
            else:
                await register_vehicle(self.faction_id, self.vehicle_name, self.designation, self.vehicle_type, self.costs, self.vehicle_data)
                title, label = f"{self.vehicle_type.title()} Registered", "Registered"
        except Exception as e:
            await interaction.followup.send(embed=error_embed("Registration Failed", str(e)), ephemeral=True)
            return
        _.label = label
        _.disabled = True
        self.stop()
        await interaction.message.edit(embed=success_embed(title, f"**{self.vehicle_name}** has been updated for **{self.faction_name}**"), view=self)
