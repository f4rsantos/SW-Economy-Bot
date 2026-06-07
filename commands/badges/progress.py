from typing import Optional
import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.currency import split_currency, handle_return
from services.badge_service import get_badge_catalog, get_badge_progress, log_badge_progress
from services.validation_service import require_faction, require_world


def _progress_bar(current: int, target: int, width: int = 10) -> str:
    filled = int(width * current / target) if target > 0 else 0
    filled = min(filled, width)
    return "█" * filled + "░" * (width - filled)


def _build_progress_embed(badge_id: int, entry: dict, current: int) -> discord.Embed:
    resource_name = next(iter(entry['costs']))
    target = entry['costs'][resource_name]
    pct = min(100, int(current * 100 / target)) if target > 0 else 0
    bar = _progress_bar(current, target)
    embed = discord.Embed(
        title=f"Badge Progress: [{entry['name']}] (ID: {badge_id})",
        description=f"{bar} {handle_return(current)} / {handle_return(target)} {resource_name} ({pct}%)",
        color=0x5865f2,
    )
    return embed


@app_commands.command(name="progress", description="Log or view your progress toward a badge")
@app_commands.describe(
    badge_id="Badge ID to contribute toward",
    amount="Amount to contribute (e.g. 500k CM). Omit to view current progress.",
    faction="Faction to deduct resources from (required when contributing)",
    world="World to deduct local resources from (required for CM/EL/CS badges)",
)
@require_access_level(0)
async def badge_progress(
    interaction: discord.Interaction,
    badge_id: int,
    amount: Optional[str] = None,
    faction: Optional[str] = None,
    world: Optional[str] = None,
):
    await interaction.response.defer()

    catalog = await get_badge_catalog()
    entry = catalog.get(badge_id)
    if not entry:
        await interaction.followup.send(embed=error_embed("Error", f"Badge {badge_id} is not a purchasable badge."))
        return

    if len(entry['costs']) > 1:
        await interaction.followup.send(embed=error_embed("Not Supported", "Progress tracking is only available for single-resource badges."))
        return

    if amount is None:
        progress = await get_badge_progress(interaction.user.id, badge_id)
        current = progress['current_amount'] if progress else 0
        await interaction.followup.send(embed=_build_progress_embed(badge_id, entry, current))
        return

    if not faction:
        await interaction.followup.send(embed=error_embed("Error", "Faction is required when contributing."))
        return

    expected_resource = next(iter(entry['costs']))
    parsed = split_currency(amount, default=expected_resource)
    if not parsed or parsed[0][0] != parsed[0][0]:
        await interaction.followup.send(embed=error_embed("Error", "Invalid amount format. Example: `500k CM`"))
        return

    contrib_amount, contrib_resource = parsed[0]
    if contrib_resource.upper() != expected_resource.upper():
        await interaction.followup.send(embed=error_embed("Error", f"This badge requires **{expected_resource}**, not {contrib_resource}."))
        return

    if contrib_amount <= 0:
        await interaction.followup.send(embed=error_embed("Error", "Amount must be greater than 0."))
        return

    r_faction = await require_faction(faction)
    if not r_faction.ok:
        await interaction.followup.send(embed=error_embed("Error", r_faction.error))
        return
    faction_data = r_faction.data

    world_id = None
    if entry['needs_world']:
        if not world:
            await interaction.followup.send(embed=error_embed("World Required", f"This badge requires local resources ({expected_resource}). Provide a `world` argument."))
            return
        r_world = await require_world(world)
        if not r_world.ok:
            await interaction.followup.send(embed=error_embed("Error", r_world.error))
            return
        world_id = r_world.data['id']
    elif world:
        r_world = await require_world(world)
        if not r_world.ok:
            await interaction.followup.send(embed=error_embed("Error", r_world.error))
            return
        world_id = r_world.data['id']

    try:
        result = await log_badge_progress(
            user_id=interaction.user.id,
            badge_id=badge_id,
            faction_id=faction_data['id'],
            world_id=world_id,
            amount=int(contrib_amount),
            catalog_entry=entry,
        )
    except ValueError as e:
        msg = str(e)
        if 'INSUFFICIENT' in msg:
            resource = msg.split(':')[1].strip().split('—')[0].strip() if ':' in msg else expected_resource
            await interaction.followup.send(embed=error_embed("Insufficient Resources", f"Not enough {resource}."))
        else:
            await interaction.followup.send(embed=error_embed("Error", msg))
        return

    if result['completed']:
        await interaction.followup.send(embed=success_embed(
            "Badge Awarded!",
            f"You've reached the goal! **[{entry['name']}]** (ID: {badge_id}) has been awarded to {interaction.user.mention}."
        ))
    else:
        await interaction.followup.send(embed=_build_progress_embed(badge_id, entry, result['current']))
