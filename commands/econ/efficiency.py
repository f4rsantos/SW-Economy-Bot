import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from services.building_efficiency_service import get_efficiency_info
from services.building_service import get_company_er
from services.validation_service import require_faction


@app_commands.command(name="efficiency", description="View faction building efficiency and specialization bonuses")
@app_commands.describe(faction="Faction name")
@require_access_level(0)
async def efficiency(interaction: discord.Interaction, faction: str):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error), ephemeral=True)
    faction_data = r_faction_data.data

    faction_id = faction_data['id']
    is_company = faction_data['is_company']
    faction_color = hex_to_int(faction_data['color'])

    info = await get_efficiency_info(faction_id)
    base_pct = int(info['base_efficiency'] * 100)

    if is_company:
        total_treasury = await get_company_er(faction_id)

        if total_treasury >= 10_000_000_000_000:
            building_cap = 600
        elif total_treasury >= 5_000_000_000_000:
            building_cap = 500
        elif total_treasury >= 1_000_000_000_000:
            building_cap = 300
        elif total_treasury >= 500_000_000_000:
            building_cap = 200
        else:
            building_cap = 100

        description = f"**Company Status:** Treasury-based building cap\n"
        description += f"**Building Units:** `{info['building_count']:,}` / `{building_cap:,}`\n"
        description += f"**Weighted Count:** `{info['building_count_weighted']:,}`\n"
    else:
        building_cap = info['building_cap']
        description = f"**Building Units:** `{info['building_count']:,}` / `{building_cap:,}`\n"
        description += f"**Weighted Count:** `{info['building_count_weighted']:,}`\n"

    if info['is_specialized']:
        spec_type = info['specialization_type'].title()
        description += f"**Efficiency:** **{base_pct}%** Base + Specialization Bonus\n"
        description += f"\n**Active Specialization: {spec_type}**\n"
        description += f"Matching buildings: **+15%** efficiency\n"
        description += f"Other buildings: **+7.5%** efficiency\n"
    else:
        description += f"**Efficiency:** **{base_pct}%** Base\n"
        description += f"\n**No Active Specialization**\n"
        description += "Get >50% of buildings in one category for bonuses:\n"
        description += "• Resource (CM/EL/CS)\n• Type (Extractor/Refinery/Storage/Factory)"

    over_cap = info['building_count'] > building_cap
    if over_cap:
        description += f"\n\n**Over building cap!** Cannot build more until cap increases."
        color = 0xff0000
    elif building_cap > 0 and info['building_count'] > building_cap * 0.9:
        description += f"\n\n**Approaching cap** ({int(info['building_count'] / (building_cap or 1) * 100)}%)"
        color = 0xffaa00
    else:
        color = faction_color

    embed = discord.Embed(title=f"{faction_data['display_name']} - Efficiency", description=description, color=color)

    brackets = "0-450: **100%**\n451-600: **100% → 85%**\n601-800: **85% → 65%**\n801+: **65% → 55%**\n\n"
    brackets += f"Current: **{base_pct}%**"
    embed.add_field(name="Efficiency System", value=brackets, inline=False)

    if info['breakdown']['by_resource']:
        resource_list = []
        for resource, count in sorted(info['breakdown']['by_resource'].items(), key=lambda x: x[1], reverse=True):
            pct = int(count / info['building_count'] * 100) if info['building_count'] > 0 else 0
            resource_list.append(f"{resource}: {count:,} ({pct}%)")
        if resource_list:
            embed.add_field(name="By Resource", value="\n".join(resource_list), inline=True)

    if info['breakdown']['by_type']:
        display_labels = {
            'city': 'City', 'refinery': 'Refinery (1.5x)', 'storage': 'Storage (5x)',
            'extractor': 'Extractor', 'factory': 'Factory (2x)', 'other': 'Other'
        }
        total_weighted = info['building_count_weighted']
        type_list = []
        for btype, count in sorted(info['breakdown']['by_type'].items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                w_count = info['breakdown']['by_type_weighted'].get(btype, 0)
                w_pct = int(w_count / total_weighted * 100) if total_weighted > 0 else 0
                type_list.append(f"{display_labels.get(btype, btype.title())}: {count:,} (**{w_pct}%**)")
        if type_list:
            embed.add_field(name="By Type", value="\n".join(type_list), inline=True)

    embed.set_footer(text=f"Territory: {info['total_hexes']:,} hexes")
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(efficiency)
