from discord import app_commands


class CometGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="comet", description="Comet discovery and exploration")


async def setup(bot):
    from commands.comets import comet_create, comet_list

    comet_group = CometGroup()
    comet_group.add_command(comet_create.comet_create)
    comet_group.add_command(comet_list.comet_list)

    bot.tree.add_command(comet_group)
