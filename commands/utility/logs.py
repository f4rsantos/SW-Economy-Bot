import discord
from discord import app_commands
from datetime import datetime
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import error_embed
from services.dashboard import _get_snapshot

ERRORS_PER_PAGE = 10
COMMANDS_PER_PAGE = 20


def _ts(iso: str) -> str:
    try:
        return f"<t:{int(datetime.fromisoformat(iso).timestamp())}:t>"
    except Exception:
        return '?'


class LogsView(discord.ui.View):
    def __init__(self, user_id: int, mode: str, snap: dict):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.mode = mode
        self.snap = snap
        self.page = 0

        if mode == "errors":
            self.items = list(reversed(snap['recent_errors']))
            self.per_page = ERRORS_PER_PAGE
        else:
            self.items = list(reversed(snap['recent_commands']))
            self.per_page = COMMANDS_PER_PAGE

        self.total_pages = max(1, (len(self.items) + self.per_page - 1) // self.per_page)
        self._update_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=error_embed("Not Allowed", "You cannot interact with someone else's command."),
            )
            return False
        return True

    def _update_buttons(self):
        self.prev_button.disabled = self.page == 0
        self.next_button.disabled = self.page >= self.total_pages - 1

    def build_embed(self) -> discord.Embed:
        total = self.snap['commands_total']
        ok    = self.snap['commands_success']
        err   = self.snap['commands_error']
        color = 0xe74c3c if err else 0x3498db

        start = self.page * self.per_page
        page_items = self.items[start:start + self.per_page]

        if self.mode == "errors":
            embed = discord.Embed(title=f"Error Log  •  {len(self.items)} total", color=color)
            if not self.items:
                embed.description = "*No errors recorded this session.*"
            else:
                lines = []
                for e in page_items:
                    lines.append(f"{_ts(e['time'])}  `/{e['command']}`  {e['user']}  —  {e['error']}")
                embed.description = "\n".join(lines)
            embed.set_footer(text=f"{err} error(s) this session  •  Page {self.page + 1}/{self.total_pages}")
        else:
            embed = discord.Embed(title=f"Command Log  •  {len(self.items)} total", color=color)
            if not self.items:
                embed.description = "*No commands recorded this session.*"
            else:
                lines = []
                for c in page_items:
                    status = "OK" if c['success'] else "ERR"
                    lines.append(f"{_ts(c['time'])}  `/{c['command']}`  {c['user']}  [{status}]")
                embed.description = "\n".join(lines)
            embed.set_footer(text=f"{total} commands  •  {ok} ok  •  {err} errors  •  Page {self.page + 1}/{self.total_pages}")

        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


@app_commands.command(name="logs", description="View bot error and command logs")
@app_commands.describe(view="What to show: errors (default) or commands")
@app_commands.choices(view=[
    app_commands.Choice(name="errors", value="errors"),
    app_commands.Choice(name="commands", value="commands"),
])
@require_access_level(9)
async def logs_command(
    interaction: discord.Interaction,
    view: Optional[app_commands.Choice[str]] = None,
):
    await interaction.response.defer()

    snap = _get_snapshot()
    mode = view.value if view else "errors"

    logs_view = LogsView(interaction.user.id, mode, snap)
    embed = logs_view.build_embed()

    if logs_view.total_pages <= 1:
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(embed=embed, view=logs_view)


async def setup(bot):
    bot.tree.add_command(logs_command)
