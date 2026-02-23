#!/usr/bin/env python3
"""
vibedroid_server.py — WebSocket terminal server for the Vibedroid Android app.

Creates a PTY, spawns a persistent tmux session ("vibedroid"), and bridges it
to WebSocket clients over HTTP so xterm.js can render it on your phone.

Usage:
    python3 vibedroid_server.py [--host 0.0.0.0] [--port 7681]
"""

import argparse
import asyncio
import fcntl
import json
import logging
import os
import pty
import struct
import sys
import termios
from typing import Set

from aiohttp import web, WSMsgType

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Terminal HTML (served at /) — xterm.js loaded from jsDelivr CDN
# ---------------------------------------------------------------------------

TERMINAL_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0,
        maximum-scale=1.0, user-scalable=no, viewport-fit=cover" />
  <title>Vibedroid</title>
  <link rel="stylesheet"
        href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css" />
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg:        #1e1e2e;
      --surface0:  #313244;
      --surface1:  #45475a;
      --surface2:  #585b70;
      --text:      #cdd6f4;
      --subtext:   #a6adc8;
      --green:     #a6e3a1;
      --red:       #f38ba8;
      --blue:      #89b4fa;
      --mauve:     #cba6f7;
      --peach:     #fab387;
    }

    html, body {
      height: 100%;
      background: var(--bg);
      color: var(--text);
      font-family: system-ui, sans-serif;
      overflow: hidden;
    }

    #app {
      display: flex;
      flex-direction: column;
      height: 100%;
      height: 100dvh; /* dynamic viewport height — respects on-screen keyboard */
    }

    #statusbar {
      background: #11111b;
      color: var(--subtext);
      font-size: 11px;
      font-family: monospace;
      padding: 2px 10px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
      user-select: none;
    }
    #statusbar .dot {
      width: 7px; height: 7px;
      border-radius: 50%;
      background: var(--surface2);
      display: inline-block;
      margin-right: 5px;
      transition: background 0.3s;
    }
    #statusbar.connected .dot { background: var(--green); }
    #statusbar.disconnected .dot { background: var(--red); }

    #terminal-wrap {
      flex: 1;
      overflow: hidden;
      position: relative;
    }

    #terminal-wrap .xterm {
      height: 100%;
    }

    /* Bottom toolbar */
    #toolbar {
      background: var(--surface0);
      border-top: 1px solid var(--surface1);
      padding: 5px 6px;
      display: flex;
      gap: 5px;
      overflow-x: auto;
      overflow-y: hidden;
      flex-shrink: 0;
      -webkit-overflow-scrolling: touch;
      scrollbar-width: none;
    }
    #toolbar::-webkit-scrollbar { display: none; }

    .btn {
      background: var(--surface1);
      color: var(--text);
      border: none;
      border-radius: 7px;
      padding: 7px 11px;
      font-size: 13px;
      font-family: monospace;
      cursor: pointer;
      white-space: nowrap;
      flex-shrink: 0;
      -webkit-tap-highlight-color: transparent;
      touch-action: manipulation;
      transition: background 0.1s, transform 0.08s;
    }
    .btn:active { background: var(--surface2); transform: scale(0.93); }
    .btn.danger  { background: #5c1a27; color: var(--red); }
    .btn.confirm { background: #1a3a27; color: var(--green); }
    .btn.special { color: var(--mauve); }
  </style>
</head>
<body>
<div id="app">
  <div id="statusbar" class="disconnected">
    <span><span class="dot"></span><span id="statustext">Connecting…</span></span>
    <span id="dimensions"></span>
  </div>

  <div id="terminal-wrap"></div>

  <div id="toolbar">
    <button class="btn danger"   onclick="ctrl('c')"      title="Ctrl+C">^C</button>
    <button class="btn danger"   onclick="ctrl('d')"      title="Ctrl+D">^D</button>
    <button class="btn special"  onclick="ctrl('z')"      title="Ctrl+Z">^Z</button>
    <button class="btn special"  onclick="ctrl('l')"      title="Ctrl+L (clear)">^L</button>
    <button class="btn"          onclick="ctrl('a')"      title="Ctrl+A (start of line)">^A</button>
    <button class="btn"          onclick="ctrl('e')"      title="Ctrl+E (end of line)">^E</button>
    <button class="btn"          onclick="sendEsc()"      title="Escape">Esc</button>
    <button class="btn"          onclick="sendTab()"      title="Tab">Tab</button>
    <button class="btn"          onclick="arrow('A')"     title="Arrow Up">↑</button>
    <button class="btn"          onclick="arrow('B')"     title="Arrow Down">↓</button>
    <button class="btn"          onclick="arrow('D')"     title="Arrow Left">←</button>
    <button class="btn"          onclick="arrow('C')"     title="Arrow Right">→</button>
    <button class="btn confirm"  onclick="send('y\\n')"  title="yes + Enter">y↵</button>
    <button class="btn danger"   onclick="send('n\\n')"  title="no + Enter">n↵</button>
    <button class="btn"          onclick="send('q\\n')"  title="q + Enter (quit pagers)">q↵</button>
    <button class="btn"          onclick="sendInput()"    title="Send custom text">⌨</button>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js"></script>
<script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js"></script>
<script>
  const term = new Terminal({
    theme: {
      background:    '#1e1e2e',
      foreground:    '#cdd6f4',
      cursor:        '#f5c2e7',
      cursorAccent:  '#1e1e2e',
      selectionBackground: 'rgba(203,166,247,0.3)',
      black:         '#45475a', brightBlack:   '#585b70',
      red:           '#f38ba8', brightRed:     '#f38ba8',
      green:         '#a6e3a1', brightGreen:   '#a6e3a1',
      yellow:        '#f9e2af', brightYellow:  '#f9e2af',
      blue:          '#89b4fa', brightBlue:    '#89b4fa',
      magenta:       '#cba6f7', brightMagenta: '#cba6f7',
      cyan:          '#89dceb', brightCyan:    '#89dceb',
      white:         '#bac2de', brightWhite:   '#a6adc8',
    },
    fontFamily: '"JetBrains Mono","Cascadia Code","Fira Code",monospace',
    fontSize: 13,
    lineHeight: 1.2,
    cursorBlink: true,
    cursorStyle: 'bar',
    scrollback: 10000,
    convertEol: false,
    allowTransparency: false,
  });

  const fitAddon = new FitAddon.FitAddon();
  term.loadAddon(fitAddon);
  term.open(document.getElementById('terminal-wrap'));
  fitAddon.fit();

  // Status bar
  const statusBar  = document.getElementById('statusbar');
  const statusText = document.getElementById('statustext');
  const dimsEl     = document.getElementById('dimensions');

  function setStatus(msg, cls) {
    statusText.textContent = msg;
    statusBar.className = cls;
    dimsEl.textContent = term.cols + '×' + term.rows;
  }

  // WebSocket
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = proto + '//' + location.host + '/ws';
  let ws = null;

  function connect() {
    ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      setStatus('Connected', 'connected');
      sendResize();
    };

    ws.onmessage = (e) => {
      if (e.data instanceof ArrayBuffer) {
        term.write(new Uint8Array(e.data));
      } else {
        term.write(e.data);
      }
    };

    ws.onclose = () => {
      setStatus('Disconnected — reconnecting…', 'disconnected');
      setTimeout(connect, 2000);
    };

    ws.onerror = () => {
      setStatus('Connection error', 'disconnected');
    };
  }

  // Terminal → WebSocket
  term.onData(data => {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(data);
  });

  function sendResize() {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
      dimsEl.textContent = term.cols + '×' + term.rows;
    }
  }

  // Resize handling
  const ro = new ResizeObserver(() => { fitAddon.fit(); sendResize(); });
  ro.observe(document.getElementById('terminal-wrap'));

  // Toolbar helpers
  function send(text)  { if (ws && ws.readyState === WebSocket.OPEN) ws.send(text); term.focus(); }
  function ctrl(k)     { send(String.fromCharCode(k.charCodeAt(0) - 96)); }
  function sendEsc()   { send('\x1b'); }
  function sendTab()   { send('\t'); }
  function arrow(dir)  { send('\x1b[' + dir); }
  function sendInput() {
    const text = prompt('Send to terminal:');
    if (text !== null) send(text);
  }

  connect();
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# PTY / session state
# ---------------------------------------------------------------------------

master_fd: int = -1
pty_clients: Set[web.WebSocketResponse] = set()


def _set_winsize(cols: int, rows: int) -> None:
    if master_fd < 0:
        return
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    try:
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
    except OSError:
        pass


def _on_pty_readable() -> None:
    """asyncio reader callback — PTY has data."""
    try:
        data = os.read(master_fd, 65536)
        if data and pty_clients:
            asyncio.ensure_future(_broadcast(data))
    except BlockingIOError:
        pass
    except OSError as exc:
        log.warning("PTY read error: %s", exc)


async def _broadcast(data: bytes) -> None:
    dead = set()
    for ws in list(pty_clients):
        try:
            await ws.send_bytes(data)
        except Exception:
            dead.add(ws)
    pty_clients.difference_update(dead)


def create_pty_session(tmux_session: str = "vibedroid") -> int:
    """
    Fork a child process that exec's tmux in a PTY.
    Returns the child PID.  Sets the global `master_fd`.
    """
    global master_fd

    mfd, sfd = pty.openpty()

    pid = os.fork()
    if pid == 0:
        # ── child ──────────────────────────────────────────────────────────
        os.close(mfd)
        os.setsid()                                    # new session
        fcntl.ioctl(sfd, termios.TIOCSCTTY, 0)        # controlling tty
        for fd in range(3):
            os.dup2(sfd, fd)
        if sfd > 2:
            os.close(sfd)
        env = os.environ.copy()
        env.update(
            TERM="xterm-256color",
            COLORTERM="truecolor",
            LANG="en_US.UTF-8",
        )
        # -A: attach if session exists; -s: session name
        os.execvpe("tmux", ["tmux", "new-session", "-A", "-s", tmux_session], env)
        os._exit(1)
    else:
        # ── parent ─────────────────────────────────────────────────────────
        os.close(sfd)
        master_fd = mfd
        # Non-blocking so add_reader callback returns quickly
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        _set_winsize(220, 50)
        log.info("PTY started — tmux session '%s' (child pid=%d)", tmux_session, pid)
        return pid


# ---------------------------------------------------------------------------
# HTTP + WebSocket handlers
# ---------------------------------------------------------------------------

async def http_root(request: web.Request) -> web.Response:
    return web.Response(text=TERMINAL_HTML, content_type="text/html")


async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    pty_clients.add(ws)
    peer = request.remote
    log.info("WS connected: %s  (total=%d)", peer, len(pty_clients))

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    obj = json.loads(msg.data)
                    if obj.get("type") == "resize":
                        _set_winsize(int(obj["cols"]), int(obj["rows"]))
                except (json.JSONDecodeError, KeyError, ValueError):
                    # Plain text → PTY stdin
                    if master_fd >= 0:
                        try:
                            os.write(master_fd, msg.data.encode())
                        except OSError:
                            pass
            elif msg.type == WSMsgType.BINARY:
                if master_fd >= 0:
                    try:
                        os.write(master_fd, msg.data)
                    except OSError:
                        pass
            elif msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE):
                break
    finally:
        pty_clients.discard(ws)
        log.info("WS disconnected: %s  (total=%d)", peer, len(pty_clients))

    return ws


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Vibedroid terminal server")
    p.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    p.add_argument("--port", type=int, default=7681, help="Port (default: 7681)")
    p.add_argument("--session", default="vibedroid", help="tmux session name")
    return p.parse_args()


async def main() -> None:
    args = parse_args()

    child_pid = create_pty_session(args.session)

    loop = asyncio.get_event_loop()
    loop.add_reader(master_fd, _on_pty_readable)

    app = web.Application()
    app.router.add_get("/",   http_root)
    app.router.add_get("/ws", ws_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, args.host, args.port)
    await site.start()

    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info("  Vibedroid server  →  http://%s:%d", args.host, args.port)
    log.info("  tmux session      →  %s", args.session)
    log.info("  Connect Android via your Tailscale IP on port %d", args.port)
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    try:
        await asyncio.Event().wait()   # run forever
    finally:
        try:
            os.kill(child_pid, 0)
        except OSError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
