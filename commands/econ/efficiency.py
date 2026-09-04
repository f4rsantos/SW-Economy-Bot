# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import error_embed, manifest_block
from utils.faction_utils import hex_to_int
from utils.autocomplete import faction_autocomplete
from services.building_efficiency_service import get_efficiency_info, round_efficiency, format_efficiency_pct, ceil_efficiency_pct, get_faction_infantry_penalty, EFFICIENCY_DECIMALS
from services.building_service import get_company_er
from services.national_spirit_service import get_national_spirits
from services.validation_service import require_faction


@app_commands.command(name="efficiency", description="View faction building efficiency and specialization bonuses")
@app_commands.describe(faction="Faction name")
@require_access_level(0)
@ephemeral_capable('faction')
async def efficiency(interaction: discord.Interaction, faction: str):
    await defer_response(interaction)

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data.id
    is_company = faction_data.is_company
    faction_color = hex_to_int(faction_data.color)

    info = await get_efficiency_info(faction_id)

    spirits = await get_national_spirits(faction_id)
    efficiency_spirits = [s for s in spirits if s.effect_type == 'efficiency']
    spirit_bonus = sum(s.modifier_value for s in efficiency_spirits)

    matching_bonus = info['specialization_matching_bonus']
    other_bonus = info['specialization_bonus']

    if info['is_specialized']:
        matching_pct = ceil_efficiency_pct(round_efficiency(info['base_efficiency'] + matching_bonus + spirit_bonus), 1)
        other_pct = ceil_efficiency_pct(round_efficiency(info['base_efficiency'] + other_bonus + spirit_bonus), 1)
    else:
        matching_pct = other_pct = ceil_efficiency_pct(round_efficiency(info['base_efficiency'] + spirit_bonus), 1)

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
    else:
        building_cap = info['building_cap']

    over_cap = info['building_count'] > building_cap
    if over_cap:
        color = 0xff0000
        footer_text = f"OVER CAP: Construction blocked | Territory: {info['total_hexes']:,} hexes"
    elif building_cap > 0 and info['building_count'] > building_cap * 0.9:
        color = 0xffaa00
        footer_text = f"Approaching cap ({int(info['building_count'] / (building_cap or 1) * 100)}%) | Territory: {info['total_hexes']:,} hexes"
    else:
        color = faction_color
        footer_text = f"Territory: {info['total_hexes']:,} hexes"

    if info['is_specialized']:
        efficiency_value = f"`{matching_pct}%` matching\n`{other_pct}%` other"
    else:
        efficiency_value = f"`{matching_pct}%`"

    fields = [
        {'name': "STRUCTURES", 'value': f"`{info['building_count']:,} / {building_cap:,}`", 'inline': True},
        {'name': "WEIGHTED", 'value': f"`{info['building_count_weighted']:,}`", 'inline': True},
        {'name': "EFFICIENCY", 'value': efficiency_value, 'inline': True},
    ]

    modifier_rows = [["Base", "100%"]]
    building_eff = info.get('building_efficiency', 1.0)
    building_penalty = max(0.0, round(1.0 - building_eff, EFFICIENCY_DECIMALS))
    building_penalty_pct = format_efficiency_pct(building_penalty, 2)
    if building_penalty_pct != "0":
        modifier_rows.append(["Buildings", f"-{building_penalty_pct}%"])

    if info['is_specialized']:
        spec_label = f"Spec ({info['specialization_type'].upper()})"
        modifier_rows.append([f"{spec_label} match", f"+{format_efficiency_pct(matching_bonus, 2)}%"])
        modifier_rows.append([f"{spec_label} other", f"+{format_efficiency_pct(other_bonus, 2)}%"])
    for s in efficiency_spirits:
        modifier_rows.append([s.display_name, f"+{format_efficiency_pct(s.modifier_value, 2)}%"])
    infantry_penalty = info.get('infantry_penalty', await get_faction_infantry_penalty(faction_id))
    infantry_penalty_pct = format_efficiency_pct(infantry_penalty, 2)
    if infantry_penalty_pct != "0":
        modifier_rows.append(["Infantry", f"-{infantry_penalty_pct}%"])

    fields.append({
        'name': "MODIFIERS",
        'value': manifest_block(modifier_rows, align=['<', '>']),
        'inline': False,
    })

    if info['breakdown']['by_resource']:
        rows = []
        for resource, count in sorted(info['breakdown']['by_resource'].items(), key=lambda x: x[1], reverse=True):
            pct = int(count / info['building_count'] * 100) if info['building_count'] > 0 else 0
            rows.append([resource, f"{count:,}", f"{pct}%"])
        if rows:
            fields.append({
                'name': "BY RESOURCE",
                'value': manifest_block(rows, headers=["RES", "QTY", "PCT"], align=['<', '>', '>']),
                'inline': True,
            })

    if info['breakdown']['by_type']:
        display_labels = {
            'city': 'City', 'refinery': 'Refinery 1.5x', 'storage': 'Storage 5x',
            'extractor': 'Extractor', 'factory': 'Factory 2x', 'other': 'Other'
        }
        total_weighted = info['building_count_weighted']
        rows = []
        for btype, count in sorted(info['breakdown']['by_type'].items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                w_count = info['breakdown']['by_type_weighted'].get(btype, 0)
                w_pct = int(w_count / total_weighted * 100) if total_weighted > 0 else 0
                rows.append([display_labels.get(btype, btype.title()), f"{count:,}", f"{w_pct}%"])
        if rows:
            fields.append({
                'name': "BY TYPE",
                'value': manifest_block(rows, headers=["TYPE", "QTY", "WGT"], align=['<', '>', '>']),
                'inline': True,
            })

    embed = discord.Embed(
        title=f"Efficiency: {faction_data.display_name}",
        color=color,
    )
    for field in fields:
        embed.add_field(name=field['name'], value=field['value'], inline=field['inline'])
    embed.set_footer(text=footer_text)

    await interaction.followup.send(embed=embed)


async def setup(bot):
    efficiency.autocomplete('faction')(faction_autocomplete)
    bot.tree.add_command(efficiency)
