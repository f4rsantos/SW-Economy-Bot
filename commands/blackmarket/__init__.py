# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands

class BlackMarketGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="blackmarket", description="Pirate black market casino")

async def setup(bot):
    from commands.blackmarket import slots, roulette, chicken, pool, blackjack, dice
    from utils.autocomplete import faction_autocomplete, world_autocomplete

    blackmarket_group = BlackMarketGroup()

    blackmarket_group.add_command(slots.slots_cmd)
    blackmarket_group.add_command(roulette.roulette_cmd)
    blackmarket_group.add_command(chicken.chicken_cmd)
    blackmarket_group.add_command(pool.pool_cmd)
    blackmarket_group.add_command(blackjack.blackjack_cmd)
    blackmarket_group.add_command(dice.dice_cmd)

    slots.slots_cmd.autocomplete('faction')(faction_autocomplete)
    slots.slots_cmd.autocomplete('world')(world_autocomplete)
    roulette.roulette_cmd.autocomplete('faction')(faction_autocomplete)
    roulette.roulette_cmd.autocomplete('world')(world_autocomplete)
    chicken.chicken_cmd.autocomplete('faction')(faction_autocomplete)
    chicken.chicken_cmd.autocomplete('world')(world_autocomplete)
    blackjack.blackjack_cmd.autocomplete('faction')(faction_autocomplete)
    blackjack.blackjack_cmd.autocomplete('world')(world_autocomplete)
    dice.dice_cmd.autocomplete('faction')(faction_autocomplete)
    dice.dice_cmd.autocomplete('world')(world_autocomplete)

    bot.tree.add_command(blackmarket_group)
