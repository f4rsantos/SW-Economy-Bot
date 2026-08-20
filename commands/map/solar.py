import discord
from discord import app_commands
import io
from typing import Optional

from utils.checks import require_access_level
from utils.embeds import error_embed
from services.solar_map_service import render_solar_map, SolarMapError


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
        image_bytes, title, game_date_label = render_solar_map(
            system_name=system,
            date_str=date,
            mode=mode,
            zoom=zoom,
            focus=focus,
        )
    except SolarMapError as e:
        await interaction.followup.send(embed=error_embed(str(e)))
        return

    file = discord.File(fp=io.BytesIO(image_bytes), filename="solar_map.png")
    embed = discord.Embed(title=title, color=0x2B2D31)
    embed.set_image(url="attachment://solar_map.png")
    embed.set_footer(text=f"In-game date: {game_date_label}")
    await interaction.followup.send(embed=embed, file=file)
