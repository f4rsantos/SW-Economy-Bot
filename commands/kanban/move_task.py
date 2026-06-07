import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed, success_embed
from services.kanban_service import move_task_to_board
from commands.kanban._utils import board_autocomplete, get_task, get_board_by_name


@app_commands.command(name="move", description="Move a task to a different board")
@app_commands.describe(
    task_id="Task ID to move",
    board="Destination board",
)
@require_access_level(0)
async def move_task_cmd(
    interaction: discord.Interaction,
    task_id: int,
    board: str,
):
    await interaction.response.defer()

    task = await get_task(task_id)
    if not task:
        await interaction.followup.send(embed=error_embed("Error", f"Task #{task_id} not found."))
        return

    board_data = await get_board_by_name(board)
    if not board_data:
        await interaction.followup.send(embed=error_embed("Error", f"Board `{board}` not found."))
        return

    if board_data['id'] == task['board_id']:
        await interaction.followup.send(embed=error_embed("Error", f"Task #{task_id} is already on **{board_data['name']}**."))
        return

    await move_task_to_board(task_id, board_data['id'])

    embed = success_embed(
        title=f"Task #{task_id} Moved",
        description=f"**{task['title']}**\n{task['board_name']} → **{board_data['name']}**"
    )
    await interaction.followup.send(embed=embed)
