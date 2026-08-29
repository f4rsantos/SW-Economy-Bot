# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
import discord
from discord import app_commands
from typing import Optional
from datetime import timezone
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return
from utils.faction_utils import hex_to_int
from utils.autocomplete import faction_autocomplete, world_autocomplete
from services.transfer_service import list_pending_transfers, get_transfer_resource_rows
from services.validation_service import require_faction, require_world
from services.user_service import get_user_access_level
from services.intelligence_service import (
    get_user_faction_id,
    has_presence_at_world,
    get_observed_worlds,
)

REF_ACCESS_LEVEL = 4


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

        embed = discord.Embed(
            title=self.title,
            description=f"Page {self.page + 1}/{self.total_pages} • {len(self.transfers)} total",
            color=self.color,
            timestamp=now
        )

        for t in page_transfers:
            arrival = t.arrival_time
            if arrival.tzinfo is None:
                arrival = arrival.replace(tzinfo=timezone.utc)

            resources = self.resources_map.get(t.id, [])
            resource_str = ", ".join(f"{handle_return(r.amount)} {r.name}" for r in resources) or "—"

            from_name, to_name = t.from_faction_name, t.to_faction_name
            if self.viewing_faction_name:
                arrow = "→" if from_name == self.viewing_faction_name else "←"
                other = to_name if from_name == self.viewing_faction_name else from_name
                header = f"Transfer #{t.id} {arrow} {other}"
            else:
                header = f"Transfer #{t.id}: {from_name} → {to_name}"

            if t.status == 'intercepted':
                blocker = t.intercepting_faction_name
                unit = t.intercepting_unit_name
                status_str = f"**INTERCEPTED**"
                if blocker:
                    status_str += f" by {blocker}"
                    if unit:
                        status_str += f" ({unit})"
                status_str += f" at {t.interception_world_name}"
            else:
                secs = int((arrival - now).total_seconds())
                if secs <= 0:
                    status_str = "**Arrived** (pending sync)"
                else:
                    d, rem = divmod(secs, 86400)
                    h, rem = divmod(rem, 3600)
                    m = rem // 60
                    status_str = f"In Transit ({f'{d}d ' if d else ''}{f'{h}h ' if h else ''}{m}min remaining)"

            escort_line = f"**Escort:** {t.escort_name}\n" if t.escort_name else ""
            embed.add_field(
                name=header,
                value=f"**Route:** {t.from_world_name} → {t.to_world_name}\n"
                      f"**Resources:** {resource_str}\n"
                      f"{escort_line}"
                      f"**Status:** {status_str}\n"
                      f"**Arrival:** <t:{int(arrival.timestamp())}:R>"
                      "
​",
                inline=False
            )
        return embed

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
    filter_type="incoming, outgoing, or all (default: all)",
    ref="Referee mode: see every transfer in full. Never private."
)
@require_access_level(0)
async def transfers_cmd(
    interaction: discord.Interaction,
    faction: Optional[str] = None,
    world: Optional[str] = None,
    filter_type: Optional[str] = "all",
    ref: bool = False
):
    await interaction.response.defer()

    if not faction and not world:
        await interaction.followup.send(embed=error_embed("Missing Filters", "Provide at least a faction or world."))
        return

    if ref:
        viewer_level = await get_user_access_level(interaction.user.id)
        if viewer_level < REF_ACCESS_LEVEL:
            await interaction.followup.send(embed=error_embed("Error", "Referee mode requires elevated access."))
            return

    viewer_faction_id = None if ref else await get_user_faction_id(interaction.user.id)

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
        faction_color = hex_to_int(faction_data.color)
        viewing_faction_name = faction_data.display_name
        title_parts.append(f"for {viewing_faction_name}")
        params.append(faction_data.id)
        world_data = r_world.data
        params.append(world_data['id'])
        title_parts.append(f"involving {world_data['name']}")
    elif faction:
        r_faction_data = await require_faction(faction)
        if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
        faction_data = r_faction_data.data
        faction_color = hex_to_int(faction_data.color)
        viewing_faction_name = faction_data.display_name
        title_parts.append(f"for {viewing_faction_name}")
        params.append(faction_data.id)
    elif world:
        r_world = await require_world(world)
        if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
        world_data = r_world.data
        params.append(world_data['id'])
        title_parts.append(f"involving {world_data['name']}")

    faction_id_param = params[0] if faction else None
    world_id_param = params[1] if faction and world else (params[0] if world else None)
    filter_type_param = (filter_type or 'all').lower()

    if not ref:
        if viewer_faction_id is None:
            await interaction.followup.send(embed=error_embed(
                "Intelligence insufficient",
                "You do not lead a faction. Use `ref:true` to view transfers openly."
            ))
            return

        if faction_id_param is not None and faction_id_param != viewer_faction_id:
            await interaction.followup.send(embed=error_embed(
                "Intelligence insufficient",
                "You can only look up your own faction. Use `ref:true` to view another faction openly."
            ))
            return

        if world_id_param is not None and not await has_presence_at_world(viewer_faction_id, world_id_param):
            await interaction.followup.send(embed=error_embed(
                "Intelligence insufficient",
                "You have no units or territory at this world."
            ))
            return

    rows = await list_pending_transfers(
        faction_id=faction_id_param,
        world_id=world_id_param,
        filter_type=filter_type_param,
    )

    if rows:
        now = discord.utils.utcnow()
        has_arrived = any(
            r.status == 'in_transit' and r.arrival_time.replace(tzinfo=timezone.utc) <= now
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

    if rows and not ref:
        observed = await get_observed_worlds(viewer_faction_id)
        rows = [
            r for r in rows
            if r.from_faction_id == viewer_faction_id
            or r.to_faction_id == viewer_faction_id
            or r.from_world_id in observed
            or r.to_world_id in observed
        ]

    if not rows:
        await interaction.followup.send(embed=success_embed("No Transfers", f"No pending transfers {' '.join(title_parts)}."))
        return

    transfer_ids = [r.id for r in rows]
    res_rows = await get_transfer_resource_rows(transfer_ids)
    resources_map: dict = {}
    for rr in res_rows:
        resources_map.setdefault(rr.transfer_id, []).append(rr)

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
