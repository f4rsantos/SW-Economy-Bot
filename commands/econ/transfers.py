import asyncio
import discord
from discord import app_commands
from typing import Optional
from datetime import timezone
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed, create_embed, panel, banner, meta_line, stamp, PANEL_W
from utils.currency import handle_return
from utils.faction_utils import hex_to_int
from utils.autocomplete import faction_autocomplete, world_autocomplete
from services.transfer_service import list_pending_transfers, get_transfer_resource_rows
from services.validation_service import require_faction, require_world


TRANSFERS_PER_PAGE = 5


class TransfersView(discord.ui.View):
    def __init__(self, transfers: list, resources_map: dict, user_id: int, title: str, color: int, viewing_faction_name: Optional[str] = None):
        super().__init__(timeout=180)
        self.transfers = transfers
        self.resources_map = resources_map
        self.user_id = user_id
        self.title = title
        self.color = color
        self.viewing_faction_name = viewing_faction_name
        self.page = 0
        self.total_pages = max(1, (len(transfers) - 1) // TRANSFERS_PER_PAGE + 1)

    def get_page_embed(self) -> discord.Embed:
        start = self.page * TRANSFERS_PER_PAGE
        page_transfers = self.transfers[start:start + TRANSFERS_PER_PAGE]
        now = discord.utils.utcnow()

        fields = []
        for t in page_transfers:
            arrival = t['arrival_time']
            if arrival.tzinfo is None:
                arrival = arrival.replace(tzinfo=timezone.utc)

            resources = self.resources_map.get(t['id'], [])
            resource_str = ", ".join(f"{handle_return(r['amount'])} {r['name']}" for r in resources) or "-"

            from_name, to_name = t['from_faction_name'], t['to_faction_name']
            stopped = t['status'] == 'intercepted'
            arrow = "===X" if stopped else "==>"

            if from_name == to_name:
                direction = "internal"
                party = None
            elif self.viewing_faction_name and from_name == self.viewing_faction_name:
                direction = "out"
                party = f"to {to_name}"
            elif self.viewing_faction_name and to_name == self.viewing_faction_name:
                direction = "in"
                party = f"from {from_name}"
            else:
                direction = "transfer"
                party = f"{from_name} to {to_name}"

            lines = [f"{t['from_world_name']} {arrow} {t['to_world_name']}"]
            if party:
                lines.append(party)
            lines.append(resource_str)

            if stopped:
                blocker = t.get('intercepting_faction_name')
                unit = t.get('intercepting_unit_name')
                held = f"held at {t['interception_world_name']}"
                if blocker:
                    held += f" by {blocker}"
                    if unit:
                        held += f" ({unit})"
                lines.append(held)
            else:
                if t.get('escort_name'):
                    lines.append(f"escort {t['escort_name']}")
                secs = int((arrival - now).total_seconds())
                lines.append("arriving now" if secs <= 0 else f"arrives {stamp(arrival, 'R')}")

            fields.append({
                'name': f"ID {t['id']} - {direction}",
                'value': "\n".join(lines),
                'inline': False,
            })

        return create_embed(
            title=self.title,
            description=panel([
                banner("Transfer Register"),
                f"{len(self.transfers)} pending",
            ]),
            color=self.color,
            fields=fields,
            footer=f"Page {self.page + 1} of {self.total_pages}",
        )

    async def _update(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(embed=error_embed("Error", "This is not your view."))
            return
        await interaction.response.edit_message(embed=self.get_page_embed(), view=self)

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page = (self.page - 1) % self.total_pages
        await self._update(interaction)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page = (self.page + 1) % self.total_pages
        await self._update(interaction)


@app_commands.command(name="transfers", description="View pending resource transfers")
@app_commands.describe(
    faction="Faction name to view transfers for",
    world="Filter by world name (origin or destination)",
    filter_type="incoming, outgoing, or all (default: all)"
)
@require_access_level(0)
async def transfers_cmd(
    interaction: discord.Interaction,
    faction: Optional[str] = None,
    world: Optional[str] = None,
    filter_type: Optional[str] = "all"
):
    await interaction.response.defer()

    if not faction and not world:
        await interaction.followup.send(embed=error_embed("Missing Filters", "Provide at least a faction or world."))
        return

    params = []
    where_parts = []
    viewing_faction_name = None
    faction_color = 0x3498db
    title_parts = []

    if faction and world:
        r_faction_data, r_world = await asyncio.gather(require_faction(faction), require_world(world))
        if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
        if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
        faction_data = r_faction_data.data
        faction_color = hex_to_int(faction_data['color'])
        viewing_faction_name = faction_data['display_name']
        title_parts.append(f"for {viewing_faction_name}")
        params.append(faction_data['id'])
        world_data = r_world.data
        params.append(world_data['id'])
        title_parts.append(f"involving {world_data['name']}")
    elif faction:
        r_faction_data = await require_faction(faction)
        if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
        faction_data = r_faction_data.data
        faction_color = hex_to_int(faction_data['color'])
        viewing_faction_name = faction_data['display_name']
        title_parts.append(f"for {viewing_faction_name}")
        params.append(faction_data['id'])
    elif world:
        r_world = await require_world(world)
        if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
        world_data = r_world.data
        params.append(world_data['id'])
        title_parts.append(f"involving {world_data['name']}")

    faction_id_param = params[0] if faction else None
    world_id_param = params[1] if faction and world else (params[0] if world else None)
    filter_type_param = (filter_type or 'all').lower()

    rows = await list_pending_transfers(
        faction_id=faction_id_param,
        world_id=world_id_param,
        filter_type=filter_type_param,
    )

    if rows:
        now = discord.utils.utcnow()
        has_arrived = any(
            r['status'] == 'in_transit' and r['arrival_time'].replace(tzinfo=timezone.utc) <= now
            for r in rows
        )
        if has_arrived:
            from services.event_queue import event_queue
            await event_queue.load_window()
            rows = await list_pending_transfers(
                faction_id=faction_id_param,
                world_id=world_id_param,
                filter_type=filter_type_param,
            )

    if not rows:
        await interaction.followup.send(embed=success_embed("No Transfers", f"No pending transfers {' '.join(title_parts)}."))
        return

    transfer_ids = [r['id'] for r in rows]
    res_rows = await get_transfer_resource_rows(transfer_ids)
    resources_map: dict = {}
    for rr in res_rows:
        resources_map.setdefault(rr['transfer_id'], []).append(rr)

    view = TransfersView(
        transfers=list(rows),
        resources_map=resources_map,
        user_id=interaction.user.id,
        title=f"Transfers: {viewing_faction_name}" if viewing_faction_name else "Transfers",
        color=faction_color,
        viewing_faction_name=viewing_faction_name
    )
    await interaction.followup.send(embed=view.get_page_embed(), view=view)


async def setup(bot):
    transfers_cmd.autocomplete('world')(world_autocomplete)
    transfers_cmd.autocomplete('faction')(faction_autocomplete)
    bot.tree.add_command(transfers_cmd)
