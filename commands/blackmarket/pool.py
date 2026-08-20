import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import log_embed, manifest_block
from utils.currency import handle_return
from services.casino_service import get_all_pools, table_max_for_pool, edge_for_pool


@app_commands.command(name="pool", description="Check the black market casino's current pool health")
@require_access_level(0)
async def pool_cmd(interaction: discord.Interaction):
    await interaction.response.defer()

    pools = await get_all_pools()

    table_rows = []
    for resource in ('ER', 'CM', 'EL', 'CS'):
        pool = pools.get(resource)
        if not pool:
            continue
        table_max = table_max_for_pool(pool['amount'], pool['floor_amount'])
        table_rows.append([resource, handle_return(pool['amount']), handle_return(table_max)])

    embed = log_embed(
        title="Casino Pool Status",
        subtitle="BLACK MARKET // HOUSE POOL",
        description=manifest_block(table_rows, headers=["RESOURCE", "POOL", "TABLE MAX"], align=['<', '>', '>']),
    )
    await interaction.followup.send(embed=embed)


async def setup(bot):
    pass
