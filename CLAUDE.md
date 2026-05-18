# Levity Voice

## MANDATORY: Always Speak Responses
**Every response Claude sends MUST be spoken aloud using the `voice_speak` tool.** This is not optional. At the end of every reply, call `voice_speak` with a natural spoken version of your response. If the response is very long, summarize the key points for the spoken version. If the response contains code or file output, speak a brief summary of what was done. Never skip this — the user relies on voice output.

---

## Development Notes

## MCP Server Process Management
- The Levity Voice MCP server (`server.py`) is NOT managed by Claude Desktop's auto-restart mechanism.
- To restart the server process: write `{"action":"restart"}` to `~/.levity-voice/command.json` — the command watcher will pick it up and `os.execv` the process.
- The bash sandbox CANNOT see or kill macOS host processes. Use the command.json restart mechanism instead.
- The menubar app (`menubar.py`) must be launched with the venv python (`~/.levity-voice/venv/bin/python`), NOT system `python3` (rumps/AppKit aren't installed there).

## Architecture
- **TTS-only mode** — voice input is handled by macOS Dictation or Claude's built-in voice input
- `server.py` — MCP server providing voice_speak and voice_toggle tools
- `menubar.py` — macOS menu bar app (separate process), communicates via file IPC:
  - Reads `config.json` for status display
  - Writes `command.json` for one-shot commands (server deletes after processing)
- Command watcher polls `command.json` every 0.5s
- Two-tier TTS: macOS `say` for short text (<200 chars), Gemini 2.5 Flash TTS for longer text

## Key File Paths
- Config: `~/.levity-voice/config.json`
- Commands: `~/.levity-voice/command.json`
- Server log: `~/.levity-voice/server.log`
- Venv: `~/.levity-voice/venv/`
