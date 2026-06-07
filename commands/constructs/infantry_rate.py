import discord
from discord import app_commands
from typing import Optional, Literal
from utils.checks import require_access_level
from utils.embeds import success_embed
from utils.currency import handle_return, handle_currency
from services.ratings.infantry_rating_service import rate_infantry


@app_commands.command(name="infantry", description="Rate infantry units")
@app_commands.describe(
    name="Name/designation of the infantry unit",
    species="Species of combatants",
    training_time="Training time in months",
    primary="Primary weapon",
    special_forces="Special forces unit",
    chemical_adaptations="Number of chemical enhancements",
    physical_adaptations="Number of physical enhancements",
    power_suit="Has power suit",
    armor="Armor level (0-10)",
    camouflage="Camouflage type",
    shield="Has shield device",
    grenades="Number of grenades",
    missiles="Number of missiles (ammo)",
    rockets="Number of rockets (ammo)",
    secondary="Secondary weapon",
    other="Other costs"
)
@require_access_level(0)
async def infantry_rate(
    interaction: discord.Interaction,
    training_time: int,
    name: Optional[str] = None,
    species: Literal["human", "robot", "catperson"] = "human",
    primary: Literal["assaultrifle", "machinegun", "sniperrifle", "sword", "staff"] = "assaultrifle",
    special_forces: bool = False,
    chemical_adaptations: int = 0,
    physical_adaptations: int = 0,
    power_suit: bool = False,
    armor: app_commands.Range[int, 0, 10] = 0,
    camouflage: Literal["none", "regular", "semiactive", "active"] = "none",
    shield: bool = False,
    grenades: int = 0,
    missiles: int = 0,
    rockets: int = 0,
    secondary: Optional[Literal["pistol", "shotgun", "rocketlauncher", "missilelauncher", "knife"]] = None,
    other: str = "0"
):
    await interaction.response.defer()

    data = {
        'species': species, 'training_time': training_time, 'primary': primary,
        'special_forces': special_forces, 'chemical_adaptations': chemical_adaptations,
        'physical_adaptations': physical_adaptations, 'power_suit': power_suit,
        'armor': armor, 'camouflage': camouflage, 'shield': shield,
        'grenades': grenades, 'missiles': missiles, 'rockets': rockets,
        'secondary': secondary, 'other': int(handle_currency(other))
    }

    costs = rate_infantry(data)

    embed = success_embed(
        title=f"Infantry: {name}" if name else "Infantry Unit",
        description=f"**{species.title()}** infantry cost calculation"
    )
    embed.add_field(name="ER Cost", value=handle_return(costs['ER']), inline=True)
    embed.add_field(
        name="Specifications",
        value=f"Species: {species} | Training: {training_time} months\n"
              f"Primary: {primary} | Secondary: {secondary or 'None'}\n"
              f"Armor: {armor}/10 | Camouflage: {camouflage}\n"
              f"Special Forces: {special_forces}",
        inline=False
    )
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(infantry_rate)
