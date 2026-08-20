import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import log_embed
from utils.currency import handle_return
from services.casino_service import get_all_pools, table_max_for_pool


@app_commands.command(name="pool", description="Check the black market casino's current pool health")
@require_access_level(0)
async def pool_cmd(interaction: discord.Interaction):
    await interaction.response.defer()

    pools = await get_all_pools()

    fields = []
    for resource in ('ER', 'CM', 'EL', 'CS'):
        pool = pools.get(resource)
        if not pool:
            continue
        table_max = table_max_for_pool(pool['amount'], pool['floor_amount'])
        fields.append({
            'name': resource,
            'value': f"Pool: {handle_return(pool['amount'])}\nMax bet: {handle_return(table_max)}",
            'inline': True,
        })

    if not fields:
        fields.append({'name': "Pools", 'value': "No pools are configured.", 'inline': False})

    embed = log_embed(
        title="Casino Pool",
        subtitle="BLACK MARKET // HOUSE POOL",
        fields=fields,
        footer="The house pays out of this pool. Bigger pools allow bigger bets.",
    )
    await interaction.followup.send(embed=embed)


async def setup(bot):
    pass
