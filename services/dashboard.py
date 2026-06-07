import json
import logging
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from collections import deque

logger = logging.getLogger(__name__)

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



_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SW-Bot Dashboard</title>
<style>
  /* ── Tokens ── */
  :root {
    --bg:        #f4f6f9;
    --surface:   #ffffff;
    --border:    #e2e6ed;
    --text:      #1a1f2e;
    --muted:     #6b7280;
    --accent:    #4f6ef7;
    --accent-bg: #eef1fe;
    --green:     #16a34a;
    --green-bg:  #dcfce7;
    --red:       #dc2626;
    --red-bg:    #fee2e2;
    --yellow:    #b45309;
    --yellow-bg: #fef3c7;
    --shadow:    0 1px 3px rgba(0,0,0,.07), 0 1px 2px rgba(0,0,0,.05);
    --radius:    10px;
  }
  [data-theme="dark"] {
    --bg:        #111318;
    --surface:   #1c1f27;
    --border:    #2a2d38;
    --text:      #e2e6f0;
    --muted:     #8b92a8;
    --accent:    #6c8fff;
    --accent-bg: #1e2640;
    --green:     #4ade80;
    --green-bg:  #052e16;
    --red:       #f87171;
    --red-bg:    #2d0a0a;
    --yellow:    #fbbf24;
    --yellow-bg: #1c1500;
    --shadow:    0 1px 4px rgba(0,0,0,.4);
  }

  /* ── Reset ── */
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  /* ── Base ── */
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    font-size: 14px;
    line-height: 1.5;
    min-height: 100vh;
    transition: background .2s, color .2s;
  }

  /* ── Layout ── */
  .page { max-width: 1120px; margin: 0 auto; padding: 28px 20px 48px; }

  /* ── Header ── */
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 28px;
  }
  .header-left h1 {
    font-size: 20px;
    font-weight: 700;
    color: var(--accent);
    letter-spacing: -0.3px;
  }
  .header-left .subtitle {
    color: var(--muted);
    font-size: 12px;
    margin-top: 2px;
  }
  .header-right { display: flex; align-items: center; gap: 10px; }

  /* ── Theme toggle ── */
  .toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 4px 12px 4px 8px;
    font-size: 12px;
    color: var(--muted);
    cursor: pointer;
    user-select: none;
    box-shadow: var(--shadow);
    transition: background .2s, border-color .2s;
  }
  .toggle:hover { border-color: var(--accent); color: var(--accent); }
  .toggle-icon { font-size: 14px; line-height: 1; }

  /* ── Refresh pill ── */
  .refresh-pill {
    font-size: 11px;
    color: var(--muted);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 3px 10px;
    box-shadow: var(--shadow);
  }

  /* ── Stat grid ── */
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
    gap: 14px;
    margin-bottom: 24px;
  }

  /* ── Cards ── */
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px 20px 16px;
    box-shadow: var(--shadow);
    transition: background .2s, border-color .2s;
  }
.card .label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .06em;
    color: var(--muted);
    margin-bottom: 4px;
  }
  .card .value {
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.5px;
    line-height: 1.1;
  }
  .card .sub {
    font-size: 12px;
    color: var(--muted);
    margin-top: 5px;
  }

  /* ── Coloured values ── */
  .c-green  { color: var(--green); }
  .c-red    { color: var(--red); }
  .c-yellow { color: var(--yellow); }
  .c-accent { color: var(--accent); }

  /* ── Progress bar ── */
  .bar-wrap {
    background: var(--border);
    border-radius: 99px;
    height: 5px;
    margin-top: 10px;
    overflow: hidden;
  }
  .bar-fill {
    height: 100%;
    border-radius: 99px;
    transition: width .5s ease;
  }

  /* ── Sections (tables) ── */
  .section {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    margin-bottom: 18px;
    overflow: hidden;
    transition: background .2s, border-color .2s;
  }
  .section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 18px 12px;
    border-bottom: 1px solid var(--border);
  }
  .section-header h2 {
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .06em;
    color: var(--muted);
  }
  .section-header .count-pill {
    font-size: 11px;
    font-weight: 600;
    background: var(--accent-bg);
    color: var(--accent);
    border-radius: 99px;
    padding: 1px 8px;
  }

  /* ── Table ── */
  table { width: 100%; border-collapse: collapse; }
  thead th {
    text-align: left;
    font-size: 11px;
    font-weight: 600;
    color: var(--muted);
    padding: 8px 18px;
    background: var(--bg);
    border-bottom: 1px solid var(--border);
  }
  tbody td {
    padding: 9px 18px;
    font-size: 13px;
    border-bottom: 1px solid var(--border);
    vertical-align: middle;
  }
  tbody tr:last-child td { border-bottom: none; }
  tbody tr:hover { background: var(--accent-bg); transition: background .1s; }
  .td-time { color: var(--muted); font-variant-numeric: tabular-nums; white-space: nowrap; }
  .td-cmd  { font-weight: 600; }
  .td-err  { color: var(--red); font-size: 12px; word-break: break-word; }
  .td-empty { text-align: center; padding: 24px; color: var(--muted); font-size: 13px; }

  /* ── Badges ── */
  .badge {
    display: inline-block;
    border-radius: 5px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: .02em;
  }
  .badge-ok  { background: var(--green-bg);  color: var(--green); }
  .badge-err { background: var(--red-bg);    color: var(--red); }

  /* ── Command split bar ── */
  .cmd-bar-wrap {
    display: flex;
    height: 6px;
    width: 100%;
    overflow: hidden;
    border-bottom: 1px solid var(--border);
  }
  .cmd-bar-ok  { background: var(--green); height: 100%; transition: width .5s ease; }
  .cmd-bar-err { background: var(--red);   height: 100%; transition: width .5s ease; }

  /* ── Footer ── */
  footer {
    text-align: center;
    color: var(--muted);
    font-size: 11px;
    margin-top: 32px;
    opacity: .7;
  }
</style>
</head>
<body>
<div class="page">

  <div class="header">
    <div class="header-left">
      <h1>SW-Bot Dashboard</h1>
      <div class="subtitle">%%bot_name%%</div>
    </div>
    <div class="header-right">
      <span class="refresh-pill" id="refresh-pill">Refreshing data…</span>
      <button class="toggle" onclick="toggleTheme()" id="themeBtn">
        <span id="themeLabel">Dark mode</span>
      </button>
    </div>
  </div>

  <!-- Stat cards -->
  <div class="grid">
    <div class="card">
      <div class="label">Status</div>
      <div class="value c-green">Online</div>
      <div class="sub">Up <span id="m-uptime">%%uptime%%</span></div>
    </div>
    <div class="card">
      <div class="label">Ping</div>
      <div class="value" id="m-ping-color">%%ping_ms%% ms</div>
      <div class="sub">Gateway latency</div>
    </div>
    <div class="card">
      <div class="label">Guilds</div>
      <div class="value c-accent" id="m-guilds">%%guild_count%%</div>
      <div class="sub">Connected servers</div>
    </div>
    <div class="card">
      <div class="label">Commands</div>
      <div class="value" id="m-commands-total">%%commands_total%%</div>
      <div class="sub"><span id="m-commands-ok">%%commands_success%%</span> ok &nbsp;·&nbsp; <span id="m-commands-err" class="%%error_color%%">%%commands_error%% errors</span></div>
      <div id="m-success-bar">%%success_bar%%</div>
    </div>
    <div class="card">
      <div class="label">Success Rate</div>
      <div class="value" id="m-rate">%%success_rate%%%</div>
      <div class="sub">Since startup</div>
    </div>
    <div class="card">
      <div class="label">Database</div>
      <div class="value" id="m-db-status">%%db_status%%</div>
      <div class="sub" id="m-db-size">%%db_size%%</div>
    </div>
    <div class="card">
      <div class="label">Cache</div>
      <div class="value c-accent" id="m-cache-factions">%%cache_factions%%</div>
      <div class="sub"><span id="m-cache-players">%%cache_players%%</span> players cached</div>
    </div>
    <div class="card">
      <div class="label">Income Runs</div>
      <div class="value" id="m-income-runs">%%income_runs%%</div>
      <div class="sub" id="m-income-last">%%income_last%%</div>
    </div>
  </div>

  <!-- Recent commands -->
  <div class="section">
    <div class="section-header">
      <h2>Recent Commands</h2>
      <span class="count-pill">last 50</span>
    </div>
    <div class="cmd-bar-wrap" id="m-cmd-bar">%%cmd_split_bar%%</div>
    <table>
      <thead><tr><th>Time (UTC)</th><th>Command</th><th>User</th><th>Result</th></tr></thead>
      <tbody id="m-cmd-rows">%%recent_commands_rows%%</tbody>
    </table>
  </div>

  <!-- Recent errors -->
  <div class="section">
    <div class="section-header">
      <h2>Recent Errors</h2>
      <span class="count-pill">last 20</span>
    </div>
    <table>
      <thead><tr><th>Time (UTC)</th><th>Command</th><th>User</th><th>Error</th></tr></thead>
      <tbody id="m-err-rows">%%recent_errors_rows%%</tbody>
    </table>
  </div>

  <!-- Uptime editor -->
  <div class="section" style="margin-bottom:18px;">
    <div class="section-header"><h2>Edit Uptime</h2></div>
    <div style="padding:16px 18px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
      <label style="font-size:13px;color:var(--muted);">Set uptime hours:</label>
      <input id="uptime-input" type="number" min="0" step="1" placeholder="e.g. 24"
        style="width:100px;padding:6px 10px;border:1px solid var(--border);border-radius:6px;
               background:var(--bg);color:var(--text);font-size:13px;outline:none;" />
      <button onclick="submitUptime()"
        style="padding:6px 16px;background:var(--accent);color:#fff;border:none;border-radius:6px;
               font-size:13px;font-weight:600;cursor:pointer;">Apply</button>
      <span id="uptime-msg" style="font-size:12px;color:var(--muted);"></span>
    </div>
  </div>

  <footer>SW-Bot Dashboard &nbsp;·&nbsp; %%now_utc%% &nbsp;·&nbsp; Made by Fer0</footer>
</div>

<script>
  // ── Theme ──
  const DARK = 'dark', LIGHT = 'light';
  const saved = localStorage.getItem('theme');
  applyTheme(saved || DARK);

  function applyTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    const label = document.getElementById('themeLabel');
    if (label) label.textContent = t === DARK ? 'Light mode' : 'Dark mode';
    localStorage.setItem('theme', t);
  }
  function toggleTheme() {
    applyTheme(document.documentElement.getAttribute('data-theme') === DARK ? LIGHT : DARK);
  }

  // ── Live data refresh (fetch /metrics, no page reload) ──
  function esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
  function fmtTime(iso) {
    if (!iso) return '—';
    try { return new Date(iso).toISOString().slice(11,19); } catch(e) { return iso; }
  }
  function colorClass(rate) {
    return rate >= 95 ? 'c-green' : rate >= 80 ? 'c-yellow' : 'c-red';
  }
  function pingClass(ms) {
    return ms < 150 ? 'c-green' : ms < 400 ? 'c-yellow' : 'c-red';
  }

  function set(id, html) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
  }
  function setClass(id, cls) {
    const el = document.getElementById(id);
    if (el) { el.className = el.className.replace(/c-\w+/g, '').trim(); if (cls) el.classList.add(cls); }
  }

  async function refreshData() {
    let m;
    try {
      const r = await fetch('/metrics');
      if (!r.ok) return;
      m = await r.json();
    } catch(e) { return; }

    if (m.started_at) _startedAt = m.started_at;

    const total = m.commands_total || 0;
    const ok    = m.commands_success || 0;
    const err   = m.commands_error || 0;
    const rate  = total ? Math.round(ok / total * 1000) / 10 : 100.0;
    const ping  = m.ping_ms || 0;

    // Stat cards
    const pingEl = document.getElementById('m-ping-color');
    if (pingEl) { pingEl.textContent = ping + ' ms'; pingEl.className = 'value ' + pingClass(ping); }

    set('m-guilds', esc(m.guild_count));
    set('m-commands-total', esc(total));
    set('m-commands-ok', esc(ok));

    const errEl = document.getElementById('m-commands-err');
    if (errEl) { errEl.textContent = err + ' errors'; errEl.className = err ? 'c-red' : ''; }

    const okPct  = total ? Math.round(ok / total * 100) : 100;
    const errPct = 100 - okPct;
    const barVar = rate >= 95 ? 'var(--green)' : rate >= 80 ? 'var(--yellow)' : 'var(--red)';
    set('m-success-bar', total
      ? `<div class="bar-wrap"><div class="bar-fill" style="width:${okPct}%;background:${barVar}"></div></div>`
      : '');

    const rateEl = document.getElementById('m-rate');
    if (rateEl) { rateEl.textContent = rate + '%'; rateEl.className = 'value ' + colorClass(rate); }

    const dbEl = document.getElementById('m-db-status');
    if (dbEl) { dbEl.textContent = m.db_connected ? 'Connected' : 'Disconnected'; dbEl.className = 'value ' + (m.db_connected ? 'c-green' : 'c-red'); }
    set('m-db-size', m.db_size_gb != null ? esc(m.db_size_gb) + ' GB' : 'size unknown');

    set('m-cache-factions', esc(m.cache_factions));
    set('m-cache-players',  esc(m.cache_players));
    set('m-income-runs',    esc(m.income_runs));
    set('m-income-last',    m.income_last_run ? 'Last: ' + fmtTime(m.income_last_run) : 'Not run yet');

    // Command split bar
    set('m-cmd-bar',
      `<div class="cmd-bar-ok" style="width:${okPct}%"></div><div class="cmd-bar-err" style="width:${errPct}%"></div>`);

    // Recent commands table
    const cmds = (m.recent_commands || []).slice().reverse();
    set('m-cmd-rows', cmds.length ? cmds.map(row =>
      `<tr><td class="td-time">${fmtTime(row.time)}</td><td class="td-cmd">/${esc(row.command)}</td><td>${esc(row.user)}</td>`+
      `<td>${row.success ? '<span class="badge badge-ok">OK</span>' : '<span class="badge badge-err">ERR</span>'}</td></tr>`
    ).join('') : '<tr><td colspan="4" class="td-empty">No commands yet</td></tr>');

    // Recent errors table
    const errs = (m.recent_errors || []).slice().reverse();
    set('m-err-rows', errs.length ? errs.map(row =>
      `<tr><td class="td-time">${fmtTime(row.time)}</td><td class="td-cmd">/${esc(row.command)}</td><td>${esc(row.user)}</td>`+
      `<td class="td-err">${esc(row.error)}</td></tr>`
    ).join('') : '<tr><td colspan="4" class="td-empty">No errors recorded</td></tr>');

    const pill = document.getElementById('refresh-pill');
    if (pill) pill.textContent = 'Updated ' + fmtTime(new Date().toISOString());
  }

  setInterval(refreshData, 10000);

  // ── Live uptime counter (ticks every second) ──
  let _startedAt = null;

  function fmtUptime(iso) {
    if (!iso) return '—';
    const total = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (total < 0) return '—';
    const d = Math.floor(total / 86400);
    const h = Math.floor((total % 86400) / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    if (d) return `${d}d ${String(h).padStart(2,'0')}h ${String(m).padStart(2,'0')}m`;
    return `${String(h).padStart(2,'0')}h ${String(m).padStart(2,'0')}m ${String(s).padStart(2,'0')}s`;
  }

  setInterval(() => {
    const el = document.getElementById('m-uptime');
    if (el && _startedAt) el.textContent = fmtUptime(_startedAt);
  }, 1000);

  // ── Uptime editor ──
  async function submitUptime() {
    const input = document.getElementById('uptime-input');
    const msg   = document.getElementById('uptime-msg');
    const hours = parseInt(input.value, 10);
    if (isNaN(hours) || hours < 0) { msg.textContent = 'Enter a valid number of hours.'; msg.style.color = 'var(--red)'; return; }
    if (!confirm(`Set bot uptime to ${hours} hour(s)? This adjusts the recorded start time.`)) return;
    try {
      const r = await fetch('/set-uptime', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({hours}) });
      if (r.ok) {
        const d = await r.json();
        _startedAt = d.started_at;
        msg.textContent = `Done — uptime set to ${hours}h.`;
        msg.style.color = 'var(--green)';
        input.value = '';
      } else {
        msg.textContent = 'Server error.';
        msg.style.color = 'var(--red)';
      }
    } catch(e) { msg.textContent = 'Request failed.'; msg.style.color = 'var(--red)'; }
    setTimeout(() => { msg.textContent = ''; }, 4000);
  }
</script>
</body>
</html>
"""


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
