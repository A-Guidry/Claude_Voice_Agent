# Levity Voice

A lightweight MCP server that gives Claude Desktop a voice. Every response is spoken aloud using a two-tier TTS system: local system TTS for short/fast replies, and Gemini 2.5 Flash TTS for longer, more natural-sounding speech.

Works on **macOS**, **Windows 11**, and **Linux**.

## Features

- **Two-tier TTS** — short text (<200 chars) uses your system's built-in TTS for instant playback; longer text uses Google Gemini 2.5 Flash TTS for high-quality, natural speech
- **Cross-platform** — macOS (`say`/`afplay`), Windows (`System.Speech.Synthesis`), and Linux (`espeak-ng`/`aplay`)
- **Stale instance management** — PID lock file detects and cleans up orphaned server processes on startup
- **Menu bar app** (macOS) — toggle the server and voice responses from the macOS menu bar
- **Zero dependencies on voice input** — works with macOS Dictation, Claude's built-in voice input, or a dedicated dictation app like [DictaFlow](https://dictaflow.app)
- **File-based IPC** — the MCP server and menu bar app communicate via atomic file operations (no sockets, no daemons)
- **Launch at login** — optional LaunchAgent integration (macOS)

## Requirements

- Python 3.10+
- Claude Desktop

### Platform-specific

| Platform | Local TTS | Audio Playback | Extra Install |
|----------|-----------|----------------|---------------|
| **macOS** | `say` (built-in) | `afplay` (built-in) | None |
| **Windows 11** | `System.Speech.Synthesis` (built-in) | `System.Media.SoundPlayer` (built-in) | None |
| **Linux** | `espeak-ng` or `espeak` | `aplay`, `paplay`, or `ffplay` | `sudo apt install espeak-ng` |

## Installation

### macOS / Linux

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/levity-voice.git ~/.levity-voice

# Create a virtual environment and install dependencies
cd ~/.levity-voice
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Windows

```powershell
# Clone the repo
git clone https://github.com/YOUR_USERNAME/levity-voice.git %USERPROFILE%\.levity-voice

# Create a virtual environment and install dependencies
cd %USERPROFILE%\.levity-voice
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Linux: install system TTS

```bash
# Debian/Ubuntu
sudo apt install espeak-ng

# Fedora
sudo dnf install espeak-ng

# Arch
sudo pacman -S espeak-ng
```

### Configure Claude Desktop

Add this to your Claude Desktop MCP config, replacing `YOUR_USERNAME` with your system username.

**macOS** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "levity-voice": {
      "command": "/Users/YOUR_USERNAME/.levity-voice/venv/bin/python",
      "args": ["/Users/YOUR_USERNAME/.levity-voice/server.py"]
    }
  }
}
```

**Windows** (`%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "levity-voice": {
      "command": "C:\\Users\\YOUR_USERNAME\\.levity-voice\\venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\YOUR_USERNAME\\.levity-voice\\server.py"]
    }
  }
}
```

**Linux** (`~/.config/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "levity-voice": {
      "command": "/home/YOUR_USERNAME/.levity-voice/venv/bin/python",
      "args": ["/home/YOUR_USERNAME/.levity-voice/server.py"]
    }
  }
}
```

> **Note:** Use the full absolute path — JSON does not expand `~`.
> Find your username: `whoami` (macOS/Linux) or `echo %USERNAME%` (Windows).

Restart Claude Desktop to pick up the new server.

### Optional: Gemini TTS

For higher-quality voice output on longer text, add a Gemini API key:

```bash
cp .env.example .env
# Edit .env and add your key (get one at https://aistudio.google.com/apikey)
```

Without a key, everything still works — it just uses macOS `say` for all text.

### Optional: Menu bar app (macOS only)

The menu bar app requires macOS (it uses `rumps` and Cocoa frameworks). On Windows and Linux, use the `voice_toggle` MCP tool to control the server instead.

```bash
# Run in the background
nohup ~/.levity-voice/venv/bin/python ~/.levity-voice/menubar.py &>/dev/null &
```

The menu bar icon lets you toggle the server and voice responses. You can also enable "Launch at Login" from the menu.

### Recommended: DictaFlow for voice input

Levity Voice handles speech *output* only — for voice *input*, we recommend [DictaFlow](https://dictaflow.app). DictaFlow is a macOS dictation app that lets you speak directly into any text field, including the Claude Desktop chat box. It provides faster, more accurate transcription than the built-in macOS Dictation and works system-wide with a configurable hotkey.

With Levity Voice + DictaFlow, you get a fully hands-free conversational loop: speak your prompt via DictaFlow, Claude responds in text, and Levity Voice reads the response back to you.

macOS Dictation (built-in, free) and Claude's native voice input also work fine if you prefer not to install another app.

## Architecture

```
┌─────────────────┐         config.json          ┌─────────────────┐
│   server.py     │◄────────(read every 0.5s)────►│   menubar.py    │
│   (MCP server)  │                               │ (macOS only)    │
│                 │◄──── command.json (write) ─────│                 │
│   voice_speak   │         (atomic rename)        │   menu toggles  │
│   voice_toggle  │                               │   launch agent  │
└─────────────────┘                               └─────────────────┘
        │
        ├── short text ──► System TTS (say / SAPI / espeak)
        └── long text  ──► Gemini 2.5 Flash TTS ──► Audio playback
```

- **server.py** — FastMCP server exposing `voice_speak` and `voice_toggle` tools. Runs inside Claude Desktop's MCP host. Cross-platform: detects macOS/Windows/Linux and uses the appropriate TTS and audio playback backends. Includes PID lock file management to prevent stale instances.
- **menubar.py** — standalone macOS menu bar app using `rumps`. Reads `config.json` for display, writes `command.json` for one-shot commands. macOS only — on other platforms, use the `voice_toggle` MCP tool directly.
- Communication is file-based IPC with atomic writes (tmp + rename) to prevent partial reads.

## Configuration

Settings live in `~/.levity-voice/config.json` (created automatically on first run):

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `server_active` | bool | `false` | Whether TTS is active |
| `response_active` | bool | `true` | Whether `voice_speak` produces audio |
| `local_voice` | string | `"Samantha"` | System voice name (macOS: `say -v ?`, Windows: see Speech settings, Linux: `espeak-ng --voices`) |
| `gemini_voice` | string | `"Kore"` | Gemini TTS voice name |

The Gemini API key is stored in `~/.levity-voice/.env` (never in `config.json`).

## MCP Tools

### `voice_speak(text, force_local=False)`
Speak text aloud. Automatically chooses local or Gemini TTS based on text length.

### `voice_toggle(action)`
Control server state. Actions: `start`, `stop`, `response_on`, `response_off`, `status`.

## License

MIT
