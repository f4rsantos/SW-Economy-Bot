# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import io
from typing import Optional
import discord
from discord import app_commands

from utils.checks import require_access_level
from utils.embeds import error_embed
from services.solar_map_service import (
    render_solar_map,
    resolve_system,
    resolve_body,
    list_pageable_bodies,
    list_focus_bodies,
    center_pan_for_body,
    SolarMapError,
)


class SolarMapView(discord.ui.View):
    def __init__(
        self,
        user_id: int,
        system: str,
        date: Optional[str],
        mode: str,
        zoom: float = 1.0,
        pan_x: float = 0.0,
        pan_y: float = 0.0,
        focus: Optional[str] = None,
    ):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.system = system
        self.date = date
        self.mode = mode
        self.zoom = zoom
        self.pan_x = pan_x
        self.pan_y = pan_y
        self.focus = focus

        canonical_system, system_data = resolve_system(system)
        canonical_focus = None
        if focus:
            try:
                canonical_focus = resolve_body(focus, system_data)
            except SolarMapError:
                canonical_focus = focus
        self.focus = canonical_focus

        self._reload_pager_bodies()
        self.index = 0
        if canonical_focus:
            for i, name in enumerate(self.bodies):
                if name.lower() == canonical_focus.lower():
                    self.index = i
                    break

        self._update_button_states()

    def _reload_pager_bodies(self):
        if self.focus:
            self.bodies = list_focus_bodies(self.system, self.focus)
        else:
            self.bodies = list_pageable_bodies(self.system)

    def _current_body(self) -> Optional[str]:
        if not self.bodies:
            return None
        return self.bodies[self.index]

    def _update_button_states(self):
        centered = self._current_body()
        if self.focus:
            self.focus_btn.label = f"Focus ({self.focus})"
            self.focus_btn.disabled = True
            self.unfocus_btn.label = "Overview"
            self.unfocus_btn.disabled = False
        else:
            if centered:
                self.focus_btn.label = f"Focus ({centered})"
            else:
                self.focus_btn.label = "Focus"
            self.focus_btn.disabled = False
            self.unfocus_btn.label = "Overview"
            self.unfocus_btn.disabled = (self.pan_x == 0 and self.pan_y == 0 and self.zoom == 1.0)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=error_embed("This is not your solar map session."),
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    async def _rerender(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            image_bytes, title, game_date_label, closest_body = render_solar_map(
                system_name=self.system,
                date_str=self.date,
                mode=self.mode,
                zoom=self.zoom,
                pan_x=self.pan_x,
                pan_y=self.pan_y,
                focus=self.focus,
            )
        except SolarMapError as e:
            await interaction.followup.send(embed=error_embed(str(e)), ephemeral=True)
            return

        self._update_button_states()

        file = discord.File(fp=io.BytesIO(image_bytes), filename="solar_map.png")
        embed = discord.Embed(title=title, color=0x2B2D31)
        embed.set_image(url="attachment://solar_map.png")

        footer_parts = [f"In-game date: {game_date_label}"]
        if self.focus:
            footer_parts.append(f"Focus: {self.focus}")

        embed.set_footer(text=" • ".join(footer_parts))
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)

    def _center_on_current(self):
        body = self._current_body()
        if body is None:
            return
        self.pan_x, self.pan_y = center_pan_for_body(
            self.system,
            body,
            date_str=self.date,
            mode=self.mode,
            zoom=self.zoom,
            focus=self.focus,
        )

    @discord.ui.button(label="Zoom In", style=discord.ButtonStyle.primary, row=0)
    async def zoom_in_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.zoom = min(round(self.zoom * 1.35, 2), 20.0)
        self._center_on_current()
        await self._rerender(interaction)

    @discord.ui.button(label="Zoom Out", style=discord.ButtonStyle.primary, row=0)
    async def zoom_out_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.zoom = max(round(self.zoom / 1.35, 2), 0.2)
        self._center_on_current()
        await self._rerender(interaction)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, row=1)
    async def previous_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if self.bodies:
            self.index = (self.index - 1) % len(self.bodies)
            self._center_on_current()
        await self._rerender(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, row=1)
    async def next_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if self.bodies:
            self.index = (self.index + 1) % len(self.bodies)
            self._center_on_current()
        await self._rerender(interaction)

    @discord.ui.button(label="Focus", style=discord.ButtonStyle.success, row=2)
    async def focus_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self.focus:
            centered = self._current_body()
            if centered:
                canonical_system, system_data = resolve_system(self.system)
                moons = [name for name, data in system_data.items() if data.get("parent") == centered]
                if moons:
                    self.focus = centered
                    self.pan_x = 0.0
                    self.pan_y = 0.0
                    self.zoom = 1.0
                    self._reload_pager_bodies()
                    self.index = 0
                else:
                    self.zoom = min(round(self.zoom * 1.8, 2), 20.0)
                    self._center_on_current()
        await self._rerender(interaction)

    @discord.ui.button(label="Overview", style=discord.ButtonStyle.secondary, row=2)
    async def unfocus_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.focus = None
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.zoom = 1.0
        self._reload_pager_bodies()
        self.index = 0
        await self._rerender(interaction)


@app_commands.command(name="solar", description="Render a 2D map of a solar system")
@app_commands.describe(
    system="Star system to render",
    date="In-game date to render (yyyy-mm-dd), defaults to the current in-game date",
    mode="Projection mode: logarithmic radius (default) or true-to-scale linear",
    zoom="Zoom multiplier for linear mode or a focus view (default 1.0)",
    focus="Center the view on this planet and show its moons instead of the full system",
)
@app_commands.choices(system=[
    app_commands.Choice(name="Sol", value="Sol"),
    app_commands.Choice(name="Corelli", value="Corelli"),
])
@app_commands.choices(mode=[
    app_commands.Choice(name="Logarithmic radius", value="log"),
    app_commands.Choice(name="Linear (true-to-scale)", value="linear"),
])
@require_access_level(0)
async def solar(
    interaction: discord.Interaction,
    system: Optional[str] = "Sol",
    date: Optional[str] = None,
    mode: Optional[str] = "log",
    zoom: Optional[float] = 1.0,
    focus: Optional[str] = None,
):
    await interaction.response.defer()

    try:
        image_bytes, title, game_date_label, closest_body = render_solar_map(
            system_name=system,
            date_str=date,
            mode=mode,
            zoom=zoom or 1.0,
            pan_x=0.0,
            pan_y=0.0,
            focus=focus,
        )
    except SolarMapError as e:
        await interaction.followup.send(embed=error_embed(str(e)))
        return

    view = SolarMapView(
        user_id=interaction.user.id,
        system=system,
        date=date,
        mode=mode or "log",
        zoom=zoom or 1.0,
        pan_x=0.0,
        pan_y=0.0,
        focus=focus,
    )

    file = discord.File(fp=io.BytesIO(image_bytes), filename="solar_map.png")
    embed = discord.Embed(title=title, color=0x2B2D31)
    embed.set_image(url="attachment://solar_map.png")

    footer_parts = [f"In-game date: {game_date_label}"]
    if focus:
        footer_parts.append(f"Focus: {focus}")

    embed.set_footer(text=" • ".join(footer_parts))
    await interaction.followup.send(embed=embed, file=file, view=view)


async def setup(bot):
    bot.tree.add_command(solar)
