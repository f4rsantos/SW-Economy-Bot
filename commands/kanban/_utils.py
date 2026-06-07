import re
import discord
from discord import app_commands
from services.kanban_service import (
    search_board_names,
    search_org_names,
    get_task as get_task_service,
    get_board_by_name as get_board_by_name_service,
    get_org_by_name as get_org_by_name_service,
)

PRIORITY_COLORS = {
    'low':      0x95a5a6,
    'medium':   0x3498db,
    'high':     0xe67e22,
    'critical': 0xe74c3c,
}

PRIORITY_LABELS = {
    'low':      'Low',
    'medium':   'Medium',
    'high':     'High',
    'critical': 'Critical',
}


def parse_user_ids(users_str: str) -> list[int]:
                                                                                
    ids = []
    for match in re.finditer(r'<@!?(\d+)>|(\b\d{17,20}\b)', users_str):
        uid = match.group(1) or match.group(2)
        if uid:
            ids.append(int(uid))
    return list(dict.fromkeys(ids))


async def board_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    names = await search_board_names(current, 25)
    return [app_commands.Choice(name=name, value=name) for name in names]


async def org_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    names = await search_org_names(current, 25)
    return [app_commands.Choice(name=name, value=name) for name in names]


async def get_task(task_id: int):
    return await get_task_service(task_id)


async def get_board_by_name(name: str):
    return await get_board_by_name_service(name)


async def get_org_by_name(name: str):
    return await get_org_by_name_service(name)
