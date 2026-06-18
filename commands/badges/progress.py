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


def _build_progress_embed(badge_id: int, entry: dict, progress: dict[str, int]) -> discord.Embed:
    lines = []
    for resource_name, target in entry['costs'].items():
        current = progress.get(resource_name, 0)
        pct = min(100, int(current * 100 / target)) if target > 0 else 0
        bar = _progress_bar(current, target)
        lines.append(f"{bar} {handle_return(current)} / {handle_return(target)} {resource_name} ({pct}%)")
    embed = discord.Embed(
        title=f"Badge Progress: [{entry['name']}] (ID: {badge_id})",
        description="\n".join(lines),
        color=0x5865f2,
    )
    return embed


@app_commands.command(name="progress", description="Log or view your progress toward a badge")
@app_commands.describe(
    badge_id="Badge ID to contribute toward",
    amount="Amount(s) to contribute (e.g. 500k CM 200k EL). Omit to view current progress.",
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

    if amount is None:
        progress = await get_badge_progress(interaction.user.id, badge_id)
        await interaction.followup.send(embed=_build_progress_embed(badge_id, entry, progress))
        return

    if not faction:
        await interaction.followup.send(embed=error_embed("Error", "Faction is required when contributing."))
        return

    expected_resources = {res.upper() for res in entry['costs']}
    default_resource = next(iter(entry['costs'])) if len(entry['costs']) == 1 else None
    parsed = split_currency(amount, default=default_resource or "")
    if not parsed or any(amt != amt for amt, _ in parsed):
        await interaction.followup.send(embed=error_embed("Error", "Invalid amount format. Example: `500k CM` or `500k CM 200k EL`"))
        return

    contributions: dict[str, int] = {}
    for contrib_amount, contrib_resource in parsed:
        if contrib_resource.upper() not in expected_resources:
            await interaction.followup.send(embed=error_embed("Error", f"This badge does not require **{contrib_resource}**. Expected: {', '.join(entry['costs'])}."))
            return
        if contrib_amount <= 0:
            await interaction.followup.send(embed=error_embed("Error", "Amount must be greater than 0."))
            return
        resource_name = next(res for res in entry['costs'] if res.upper() == contrib_resource.upper())
        contributions[resource_name] = contributions.get(resource_name, 0) + int(contrib_amount)

    r_faction = await require_faction(faction)
    if not r_faction.ok:
        await interaction.followup.send(embed=error_embed("Error", r_faction.error))
        return
    faction_data = r_faction.data

    world_id = None
    if entry['needs_world']:
        if not world:
            await interaction.followup.send(embed=error_embed("World Required", f"This badge requires local resources ({', '.join(entry['costs'])}). Provide a `world` argument."))
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
            contributions=contributions,
            catalog_entry=entry,
        )
    except ValueError as e:
        msg = str(e)
        if 'INSUFFICIENT' in msg:
            resource = msg.split(':')[1].strip().split('—')[0].strip() if ':' in msg else next(iter(contributions))
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
        await interaction.followup.send(embed=_build_progress_embed(badge_id, entry, result['progress']))
