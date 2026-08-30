# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from discord import app_commands


class MegaprojectGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="megaproject", description="Megaproject commands")


async def setup(bot):
    from commands.megaproject import build, contribute, list_megaprojects, view, lane, port_access
    from utils.autocomplete import faction_autocomplete, port_world_autocomplete

    megaproject_group = MegaprojectGroup()
    megaproject_group.add_command(build.build_megaproject)
    megaproject_group.add_command(contribute.contribute_megaproject)
    megaproject_group.add_command(list_megaprojects.list_megaprojects)
    megaproject_group.add_command(view.view_megaproject)
    megaproject_group.add_command(view.view_megaproject_progress)
    megaproject_group.add_command(lane.build_lane)
    megaproject_group.add_command(lane.list_lanes)
    megaproject_group.add_command(port_access.port_access_set)
    megaproject_group.add_command(port_access.port_access_clear)
    megaproject_group.add_command(port_access.port_access_list)

    lane.build_lane.autocomplete('faction')(faction_autocomplete)
    lane.build_lane.autocomplete('port_world_a')(port_world_autocomplete)
    lane.build_lane.autocomplete('port_world_b')(port_world_autocomplete)
    lane.list_lanes.autocomplete('faction')(faction_autocomplete)

    port_access.port_access_set.autocomplete('faction')(faction_autocomplete)
    port_access.port_access_set.autocomplete('port_world')(port_world_autocomplete)
    port_access.port_access_set.autocomplete('other_faction')(faction_autocomplete)
    port_access.port_access_clear.autocomplete('faction')(faction_autocomplete)
    port_access.port_access_clear.autocomplete('port_world')(port_world_autocomplete)
    port_access.port_access_clear.autocomplete('other_faction')(faction_autocomplete)
    port_access.port_access_list.autocomplete('faction')(faction_autocomplete)
    port_access.port_access_list.autocomplete('port_world')(port_world_autocomplete)

    bot.tree.add_command(megaproject_group)
