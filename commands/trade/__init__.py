# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands

class TradeGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="trade", description="Trade management commands")

async def setup(bot):
    from commands.trade import trades, begin_trade, end_trade

    trade_group = TradeGroup()

    trade_group.add_command(trades.trades)
    trade_group.add_command(begin_trade.begin_trade)
    trade_group.add_command(end_trade.end_trade)
    
    bot.tree.add_command(trade_group)
