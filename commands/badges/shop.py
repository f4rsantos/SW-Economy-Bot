from typing import Optional
import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return
from utils.faction_utils import hex_to_int
from services.user_service import get_user_access_level
from services.badge_service import get_badge_catalog, purchase_badge
from services.validation_service import require_faction, require_world


def _format_costs(costs: dict) -> str:
    return ", ".join(f"{handle_return(v)} {k}" for k, v in costs.items())


async def _is_faction_leader(user_id: int, faction: dict) -> bool:
    if faction.get('leader_id') == user_id:
        return True
    return await get_user_access_level(user_id) >= 4


class BadgeShopView(discord.ui.View):
    def __init__(self, owner_id: int, faction: dict, world_id: Optional[int],
                 catalog: dict[int, dict], faction_color: int):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.faction = faction
        self.world_id = world_id
        self.catalog = catalog
        self.faction_color = faction_color
        self.selected_badge_id: Optional[int] = None

        options = []
        for badge_id, entry in catalog.items():
            cost_str = _format_costs(entry['costs'])
            options.append(discord.SelectOption(
                label=f"[{entry['name']}] (ID: {badge_id})",
                value=str(badge_id),
                description=cost_str[:100],
            ))
        self.badge_select.options = options

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                embed=error_embed("Not Allowed", "You cannot interact with someone else's command."),
            )
            return False
        return True

    @discord.ui.select(placeholder="Select a badge to buy…", min_values=1, max_values=1, options=[])
    async def badge_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.selected_badge_id = int(select.values[0])
        await interaction.response.defer()

    @discord.ui.button(label="Buy", style=discord.ButtonStyle.green)
    async def buy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.selected_badge_id is None:
            await interaction.response.send_message(
                embed=error_embed("No Badge Selected", "Select a badge from the dropdown first."),
            )
            return

        if not await _is_faction_leader(interaction.user.id, self.faction):
            await interaction.response.send_message(
                embed=error_embed("Access Denied", "Only faction leaders can buy badges."),
            )
            return

        entry = self.catalog[self.selected_badge_id]
        if entry['needs_world'] and self.world_id is None:
            await interaction.response.send_message(
                embed=error_embed("World Required", "This badge costs local resources (CM/EL/CS). Re-run `/badge shop` with a `world` argument."),
            )
            return

        await interaction.response.defer()

        try:
            await purchase_badge(self.faction['id'], self.world_id, self.selected_badge_id, interaction.user.id)
        except ValueError as e:
            msg = str(e)
            if 'INSUFFICIENT' in msg:
                resource = msg.split(':')[1].strip().split('—')[0].strip() if ':' in msg else 'resources'
                await interaction.followup.send(embed=error_embed("Insufficient Resources", f"Not enough {resource}."))
            else:
                await interaction.followup.send(embed=error_embed("Error", msg))
            return

        badge_name = entry['name']
        cost_str = _format_costs(entry['costs'])

        button.disabled = True
        self.badge_select.disabled = True
        self.stop()

        embed = success_embed(
            title="Badge Purchased",
            description=f"**{interaction.user.mention}** bought **[{badge_name}]** (ID: {self.selected_badge_id}) for **{self.faction['display_name']}**\n\n**Cost:** {cost_str}"
        )
        embed.color = self.faction_color
        await interaction.message.edit(embed=embed, view=self)


def _build_shop_embed(faction: dict, catalog: dict[int, dict], faction_color: int) -> discord.Embed:
    embed = discord.Embed(
        title="Badge Shop",
        description=f"**{faction['display_name']}**\n\nSelect a badge and click **Buy**. Only faction leaders can purchase.",
        color=faction_color,
    )
    for badge_id, entry in catalog.items():
        cost_str = _format_costs(entry['costs'])
        world_note = " *(requires world)*" if entry['needs_world'] else ""
        embed.add_field(name=f"[{entry['name']}] (ID: {badge_id})", value=f"{cost_str}{world_note}", inline=False)
    return embed


@app_commands.command(name="shop", description="Browse and buy badges for your faction")
@app_commands.describe(
    faction="Faction name",
    world="World for local resource costs (required for badges with CM/EL/CS costs)",
)
@require_access_level(0)
async def badge_shop(
    interaction: discord.Interaction,
    faction: str,
    world: Optional[str] = None,
):
    await interaction.response.defer()

    r_faction = await require_faction(faction)
    if not r_faction.ok:
        return await interaction.followup.send(embed=error_embed("Error", r_faction.error))
    faction_data = r_faction.data
    faction_color = hex_to_int(faction_data['color'])

    world_id = None
    if world:
        r_world = await require_world(world)
        if not r_world.ok:
            return await interaction.followup.send(embed=error_embed("Error", r_world.error))
        world_id = r_world.data['id']

    catalog = await get_badge_catalog()
    if not catalog:
        return await interaction.followup.send(embed=error_embed("No Badges", "No purchasable badges available."))

    embed = _build_shop_embed(faction_data, catalog, faction_color)
    view = BadgeShopView(interaction.user.id, faction_data, world_id, catalog, faction_color)
    await interaction.followup.send(embed=embed, view=view)


async def setup(bot):
    pass
