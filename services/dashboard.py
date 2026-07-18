import json
import logging
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from collections import deque
from utils.config_encryption import get_bundle_dir

logger = logging.getLogger(__name__)


def _load_template() -> str:
    return (get_bundle_dir() / "services" / "dashboard_template.html").read_text(encoding="utf-8")


_HTML = _load_template()

_metrics = {
    'bot_name': 'Unknown',
    'bot_id': None,
    'bot_version': '',
    'guild_count': 0,
    'started_at': None,
    'ping_ms': 0.0,
    'commands_total': 0,
    'commands_success': 0,
    'commands_error': 0,
    'last_command_at': None,
    'recent_errors': deque(maxlen=20),
    'recent_commands': deque(maxlen=50),
    'db_connected': False,
    'db_size_gb': None,
    'cache_factions': 0,
    'cache_players': 0,
    'income_last_run': None,
    'income_runs': 0,
}

_lock = threading.Lock()


def record_command(command_name: str, user_tag: str):
    with _lock:
        _metrics['commands_total'] += 1
        _metrics['commands_success'] += 1
        now = datetime.now(timezone.utc).isoformat()
        _metrics['last_command_at'] = now
        _metrics['recent_commands'].append({
            'time': now,
            'command': command_name,
            'user': user_tag,
            'success': True,
        })


def record_command_error(command_name: str, user_tag: str, error_str: str = None):
    with _lock:
        _metrics['commands_success'] = max(0, _metrics['commands_success'] - 1)
        _metrics['commands_error'] += 1
        now = datetime.now(timezone.utc).isoformat()
        for entry in reversed(_metrics['recent_commands']):
            if entry['command'] == command_name and entry['user'] == user_tag and entry['success']:
                entry['success'] = False
                break
        if error_str:
            _metrics['recent_errors'].append({
                'time': now,
                'command': command_name,
                'user': user_tag,
                'error': error_str[:300],
            })


def update_bot_info(bot_name: str, bot_id: int, guild_count: int, ping_ms: float, bot_version: str = None):
    with _lock:
        _metrics['bot_name'] = bot_name
        _metrics['bot_id'] = bot_id
        if bot_version is not None:
            _metrics['bot_version'] = bot_version
        _metrics['guild_count'] = guild_count
        _metrics['ping_ms'] = round(ping_ms, 1)


def update_db_info(connected: bool, size_gb: float = None):
    with _lock:
        _metrics['db_connected'] = connected
        if size_gb is not None:
            _metrics['db_size_gb'] = round(size_gb, 4)


def update_cache_info(factions: int, players: int):
    with _lock:
        _metrics['cache_factions'] = factions
        _metrics['cache_players'] = players


def record_income_run():
    with _lock:
        _metrics['income_last_run'] = datetime.now(timezone.utc).isoformat()
        _metrics['income_runs'] += 1


def set_started():
    with _lock:
        _metrics['started_at'] = datetime.now(timezone.utc).isoformat()


_flags: dict = {}

def set_flags(**kwargs):
    with _lock:
        _flags.update(kwargs)

def get_flags() -> dict:
    with _lock:
        return dict(_flags)


def _get_snapshot():
    with _lock:
        snap = dict(_metrics)
        snap['recent_errors'] = list(snap['recent_errors'])
        snap['recent_commands'] = list(snap['recent_commands'])
    return snap





def _uptime_str(started_at_iso: str) -> str:
    if not started_at_iso:
        return '—'
    started = datetime.fromisoformat(started_at_iso)
    delta = datetime.now(timezone.utc) - started
    total = int(delta.total_seconds())
    d, rem = divmod(total, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    if d:
        return f"{d}d {h:02d}h {m:02d}m"
    return f"{h:02d}h {m:02d}m {s:02d}s"


def _fmt_time(iso: str) -> str:
    if not iso:
        return '—'
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime('%H:%M:%S')
    except Exception:
        return iso


def _render(snap: dict) -> str:
    total = snap['commands_total']
    ok = snap['commands_success']
    err = snap['commands_error']
    rate = round(ok / total * 100, 1) if total else 100.0
    rate_color = 'c-green' if rate >= 95 else ('c-yellow' if rate >= 80 else 'c-red')
    error_color = 'c-red' if err else ''
    ping = snap['ping_ms']
    ping_color = 'c-green' if ping < 150 else ('c-yellow' if ping < 400 else 'c-red')

    bar_pct = int(rate)
    bar_var = 'var(--green)' if rate >= 95 else ('var(--yellow)' if rate >= 80 else 'var(--red)')
    success_bar = (
        f'<div class="bar-wrap"><div class="bar-fill" style="width:{bar_pct}%;background:{bar_var}"></div></div>'
        if total else ''
    )

    db_color = 'c-green' if snap['db_connected'] else 'c-red'
    db_status = 'Connected' if snap['db_connected'] else 'Disconnected'
    db_size = f"{snap['db_size_gb']} GB" if snap['db_size_gb'] is not None else 'size unknown'

    income_last = f"Last: {_fmt_time(snap['income_last_run'])}" if snap['income_last_run'] else 'Not run yet'

    ok_pct = round(ok / total * 100) if total else 100
    err_pct = 100 - ok_pct
    cmd_split_bar = (
        f'<div class="cmd-bar-ok" style="width:{ok_pct}%"></div>'
        f'<div class="cmd-bar-err" style="width:{err_pct}%"></div>'
    ) if total else '<div class="cmd-bar-ok" style="width:100%"></div>'

    cmd_rows = ''
    for row in reversed(snap['recent_commands']):
        badge = '<span class="badge badge-ok">OK</span>' if row['success'] else '<span class="badge badge-err">ERR</span>'
        cmd_rows += (
            f'<tr>'
            f'<td class="td-time">{_fmt_time(row["time"])}</td>'
            f'<td class="td-cmd">/{_escape(row["command"])}</td>'
            f'<td>{_escape(row["user"])}</td>'
            f'<td>{badge}</td>'
            f'</tr>\n'
        )
    if not cmd_rows:
        cmd_rows = '<tr><td colspan="4" class="td-empty">No commands yet</td></tr>'

    err_rows = ''
    for row in reversed(snap['recent_errors']):
        err_rows += (
            f'<tr>'
            f'<td class="td-time">{_fmt_time(row["time"])}</td>'
            f'<td class="td-cmd">/{_escape(row["command"])}</td>'
            f'<td>{_escape(row["user"])}</td>'
            f'<td class="td-err">{_escape(row["error"])}</td>'
            f'</tr>\n'
        )
    if not err_rows:
        err_rows = '<tr><td colspan="4" class="td-empty">No errors recorded</td></tr>'

    replacements = {
        '%%bot_name%%':            _escape(snap['bot_name']),
        '%%uptime%%':              _uptime_str(snap['started_at']),
        '%%ping_ms%%':             str(ping),
        '%%ping_color%%':          ping_color,
        '%%guild_count%%':         str(snap['guild_count']),
        '%%commands_total%%':      str(total),
        '%%commands_success%%':    str(ok),
        '%%commands_error%%':      str(err),
        '%%error_color%%':         error_color,
        '%%success_bar%%':         success_bar,
        '%%success_rate%%':        str(rate),
        '%%rate_color%%':          rate_color,
        '%%db_color%%':            db_color,
        '%%db_status%%':           db_status,
        '%%db_size%%':             db_size,
        '%%cache_factions%%':      str(snap['cache_factions']),
        '%%cache_players%%':       str(snap['cache_players']),
        '%%income_runs%%':         str(snap['income_runs']),
        '%%income_last%%':         income_last,
        '%%cmd_split_bar%%':        cmd_split_bar,
        '%%recent_commands_rows%%': cmd_rows,
        '%%recent_errors_rows%%':  err_rows,
        '%%now_utc%%':             datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
    }
    out = _HTML
    for token, value in replacements.items():
        out = out.replace(token, value)
    return out


def _escape(s: str) -> str:
    if not s:
        return ''
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def set_uptime_hours(hours: int):
    with _lock:
        from datetime import timedelta
        new_start = datetime.now(timezone.utc) - timedelta(hours=hours)
        _metrics['started_at'] = new_start.isoformat()
        return _metrics['started_at']


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ('/', '/metrics'):
            self.send_response(404)
            self.end_headers()
            return

        snap = _get_snapshot()

        if self.path == '/metrics':
            body = json.dumps(snap, default=str).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = _render(snap).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def do_POST(self):
        if self.path == '/set-uptime':
            try:
                length = int(self.headers.get('Content-Length', 0))
                data = json.loads(self.rfile.read(length))
                hours = int(data['hours'])
                if hours < 0:
                    raise ValueError
            except Exception:
                self.send_response(400)
                self.end_headers()
                return
            started_at = set_uptime_hours(hours)
            body = json.dumps({'ok': True, 'started_at': started_at}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass



_server_instance: HTTPServer = None


def start_dashboard(port: int = 8088):
    global _server_instance
    set_started()

    server = HTTPServer(('127.0.0.1', port), _Handler)
    _server_instance = server

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    import webbrowser
    webbrowser.open(f'http://localhost:{port}')
    logger.info(f"Dashboard running at http://localhost:{port}")
