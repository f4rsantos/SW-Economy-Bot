from discord import app_commands


class CometGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="comet", description="Comet discovery and exploration")


async def setup(bot):
    from commands.comets import cometCreate, cometList

    comet_group = CometGroup()
    comet_group.add_command(cometCreate.comet_create)
    comet_group.add_command(cometList.comet_list)

    bot.tree.add_command(comet_group)
