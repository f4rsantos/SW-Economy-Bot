# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import io
import math
from typing import Optional
import discord
from discord import app_commands

from utils.checks import require_access_level
from utils.embeds import error_embed
from services.solar_map_service import (
    render_solar_map,
    resolve_system,
    SolarMapError,
    radial_pan_step,
    angular_pan_step,
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
        closest_body: Optional[str] = None,
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
        self.closest_body = closest_body
        self._update_button_states()

    def _update_button_states(self):
        if self.focus:
            self.focus_btn.label = f"⊙ Focus ({self.focus})"
            self.focus_btn.disabled = True
            self.unfocus_btn.label = "↺ Overview"
            self.unfocus_btn.disabled = False
        else:
            if self.closest_body:
                self.focus_btn.label = f"⊙ Focus ({self.closest_body})"
            else:
                self.focus_btn.label = "⊙ Focus"
            self.focus_btn.disabled = False
            self.unfocus_btn.label = "↺ Overview"
            self.unfocus_btn.disabled = (self.pan_x == 0 and self.pan_y == 0 and self.zoom == 1.0)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=error_embed("This is not your solar map session."),
                ephemeral=True
            )
            return False
        return True

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

        self.closest_body = closest_body
        self._update_button_states()

        file = discord.File(fp=io.BytesIO(image_bytes), filename="solar_map.png")
        embed = discord.Embed(title=title, color=0x2B2D31)
        embed.set_image(url="attachment://solar_map.png")

        footer_parts = [f"In-game date: {game_date_label}"]
        if self.focus:
            footer_parts.append(f"Focus: {self.focus}")

        embed.set_footer(text=" • ".join(footer_parts))
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)

    @discord.ui.button(label="＋ In", style=discord.ButtonStyle.primary, row=0)
    async def zoom_in_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.zoom = min(round(self.zoom * 1.35, 2), 20.0)
        await self._rerender(interaction)

    @discord.ui.button(label="－ Out", style=discord.ButtonStyle.primary, row=0)
    async def zoom_out_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.zoom = max(round(self.zoom / 1.35, 2), 0.2)
        await self._rerender(interaction)

    @discord.ui.button(label="◆ In", style=discord.ButtonStyle.secondary, row=1)
    async def radial_in_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        step = max(60, int(300 / math.sqrt(self.zoom)))
        self.pan_x, self.pan_y = radial_pan_step(self.pan_x, self.pan_y, step, "in")
        await self._rerender(interaction)

    @discord.ui.button(label="◇ Out", style=discord.ButtonStyle.secondary, row=1)
    async def radial_out_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        step = max(60, int(300 / math.sqrt(self.zoom)))
        self.pan_x, self.pan_y = radial_pan_step(self.pan_x, self.pan_y, step, "out")
        await self._rerender(interaction)

    @discord.ui.button(label="↺ CCW", style=discord.ButtonStyle.secondary, row=1)
    async def rotate_ccw_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        step = max(60, int(300 / math.sqrt(self.zoom)))
        self.pan_x, self.pan_y = angular_pan_step(self.pan_x, self.pan_y, step, "ccw")
        await self._rerender(interaction)

    @discord.ui.button(label="↻ CW", style=discord.ButtonStyle.secondary, row=1)
    async def rotate_cw_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        step = max(60, int(300 / math.sqrt(self.zoom)))
        self.pan_x, self.pan_y = angular_pan_step(self.pan_x, self.pan_y, step, "cw")
        await self._rerender(interaction)

    @discord.ui.button(label="⊙ Focus", style=discord.ButtonStyle.success, row=2)
    async def focus_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self.focus and self.closest_body:
            canonical_system, system_data = resolve_system(self.system)
            moons = [name for name, data in system_data.items() if data.get("parent") == self.closest_body]
            if moons:
                self.focus = self.closest_body
                self.pan_x = 0.0
                self.pan_y = 0.0
                self.zoom = 1.0
            else:
                self.zoom = min(round(self.zoom * 1.8, 2), 20.0)
        await self._rerender(interaction)

    @discord.ui.button(label="↺ Overview", style=discord.ButtonStyle.secondary, row=2)
    async def unfocus_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.focus = None
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.zoom = 1.0
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
        closest_body=closest_body,
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

