# Vibedroid

Mirror your terminal (including Claude Code sessions) to your Android phone via Tailscale.

```
┌──────────────────────────────────────┐
│  WSL (Ubuntu)                        │
│  ┌────────────────────────────────┐  │
│  │ tmux "vibedroid" session       │  │
│  │  → claude code running here    │  │
│  └─────────────┬──────────────────┘  │
│                │ PTY                 │
│  ┌─────────────▼──────────────────┐  │
│  │ vibedroid_server.py            │  │
│  │  HTTP :7681  →  terminal.html  │  │
│  │  WS   :7681/ws  ←→  xterm.js  │  │
│  └─────────────┬──────────────────┘  │
└────────────────│─────────────────────┘
                 │ Tailscale VPN
┌────────────────▼─────────────────────┐
│  Android phone                       │
│  Vibedroid app  →  WebView           │
│  (xterm.js renders the terminal)     │
└──────────────────────────────────────┘
```

## How it works

- The Python server creates a **PTY** (pseudo-terminal) and forks a `tmux` session inside it.
- `tmux` provides **session persistence**: if you close the app or lose connection, the session keeps running and you reconnect to the same state.
- Terminal output is streamed as raw bytes over a **WebSocket** to the Android WebView.
- **xterm.js** in the WebView renders ANSI/VT100 escape codes perfectly.
- The toolbar gives one-tap access to the keys most useful for Claude Code: `^C`, `^D`, `y↵`, `n↵`, arrow keys, Tab, etc.

---

## Setup: Server (WSL/Ubuntu)

### 1. Install dependencies

```bash
# tmux (if not already installed)
sudo apt install tmux

# Python deps
cd ~/vibedroid/server
pip3 install -r requirements.txt
```

### 2. Find your Tailscale IP

```bash
tailscale ip -4
# → 100.x.x.x  ← this is what you enter in the Android app
```

### 3. Start the server

```bash
cd ~/vibedroid/server
bash install.sh
# or directly:
python3 vibedroid_server.py
```

The server starts on `0.0.0.0:7681`. It creates (or attaches to) a tmux session named `vibedroid`.

**To run Claude Code inside the managed session:**

```bash
# In a separate terminal, attach to the vibedroid tmux session:
tmux attach -t vibedroid
# Then run claude code as usual:
claude
```

Or start it before launching the server:
```bash
tmux new-session -d -s vibedroid "claude"
python3 vibedroid_server.py
```

### 4. Auto-start on WSL login (optional)

Add to your `~/.bashrc` or `~/.profile`:

```bash
# Start vibedroid server in background if not already running
if ! pgrep -f vibedroid_server.py > /dev/null; then
    nohup python3 ~/vibedroid/server/vibedroid_server.py \
        > ~/vibedroid/server/vibedroid.log 2>&1 &
fi
```

---

## Setup: Android App

### Requirements
- Android Studio (Hedgehog / 2023.1 or newer)
- Android phone with Android 8.0+ (API 26+)
- Connected to Tailscale

### Build and install

1. Open Android Studio
2. **File → Open** → select the `android/` folder
3. Wait for Gradle sync to finish
4. Connect your Android phone via USB (or use an emulator)
5. Click **Run ▶**

### First-time app setup

1. Tap **+** to add a connection
2. Enter a name (e.g. "WSL Dev"), your **Tailscale IP** (`100.x.x.x`), and port `7681`
3. Tap **Save Connection**
4. Tap the connection to open the terminal

---

## Using with Claude Code

**Typical workflow:**

1. Start the vibedroid server on your WSL machine
2. Inside the tmux session, run `claude` (or whatever you're working on)
3. Open the Vibedroid app on your phone → tap your connection
4. You see the terminal — xterm.js renders colors, progress bars, and all Claude output faithfully

**Toolbar quick actions:**

| Button | Sends | Use case |
|--------|-------|----------|
| `^C`   | Ctrl+C | Interrupt / cancel current operation |
| `^D`   | Ctrl+D | End of input |
| `^Z`   | Ctrl+Z | Suspend process |
| `^L`   | Ctrl+L | Clear screen |
| `^A`   | Ctrl+A | Jump to start of line |
| `^E`   | Ctrl+E | Jump to end of line |
| `Esc`  | Escape | Exit modes in vim/less |
| `Tab`  | Tab | Shell autocomplete |
| `↑ ↓ ← →` | Arrow keys | Command history / navigation |
| `y↵`  | `y` + Enter | Confirm Claude prompts |
| `n↵`  | `n` + Enter | Deny Claude prompts |
| `q↵`  | `q` + Enter | Quit pagers (less, man) |
| `⌨`   | Custom text | Send any text via popup |

**Session persistence:** The tmux session keeps running even if you close the app. When you reconnect, you pick up exactly where you left off — including any running Claude Code process.

---

## Troubleshooting

**Can't connect from phone:**
- Confirm the server is running: `curl http://100.x.x.x:7681`
- Check Tailscale is connected on both devices: `tailscale status`
- WSL firewall: `sudo ufw allow 7681` (if ufw is active)

**Terminal looks garbled:**
- The session uses `TERM=xterm-256color`. Make sure your shell/app respects this.
- Try resizing the terminal (rotate phone or resize the browser window).

**tmux session not found:**
- `tmux list-sessions` to check what sessions exist
- The server creates a session named `vibedroid` by default; change with `--session`

**Server exits immediately:**
- Make sure `tmux` is installed: `which tmux`
- Check `vibedroid.log` for error output

---

## Architecture notes

- The server forks a child process that exec's `tmux` inside a Linux PTY. The master fd is held by the server and read with `asyncio`'s `add_reader` for zero-copy non-blocking I/O.
- All connected WebSocket clients receive the same PTY byte stream — you can have the server tab open in a browser AND the Android app simultaneously.
- Terminal resize messages (`{type:"resize",cols,rows}`) are forwarded to the PTY via `TIOCSWINSZ` ioctl so the shell and Claude Code reflow output correctly.
- The app uses `android:usesCleartextTraffic="true"` to allow plain `http://` to the Tailscale IP (which is a private VPN — no risk).
# vibedroid
