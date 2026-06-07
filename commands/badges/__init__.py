from discord import app_commands


class BadgeGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="badge", description="Badge commands")


async def setup(bot):
    from commands.badges import shop, badges_util, progress

    badge_group = BadgeGroup()
    badge_group.add_command(shop.badge_shop)
    badge_group.add_command(badges_util.new_badge)
    badge_group.add_command(badges_util.add_badge)
    badge_group.add_command(badges_util.remove_badge)
    badge_group.add_command(badges_util.list_badges)
    badge_group.add_command(progress.badge_progress)

    bot.tree.add_command(badge_group)
