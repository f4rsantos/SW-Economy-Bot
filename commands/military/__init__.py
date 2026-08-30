# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from discord import app_commands


class MilitaryGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="military", description="Military management commands")


async def setup(bot):
    from commands.military import recruit, dismiss, transfer, progress, cancel

    military_group = MilitaryGroup()
    military_group.add_command(recruit.recruit)
    military_group.add_command(dismiss.dismiss)
    military_group.add_command(transfer.transfer)
    military_group.add_command(progress.progress)
    military_group.add_command(cancel.cancel)

    bot.tree.add_command(military_group)
