# Multi-Host Voice Daemon

Lets Levity run in Claude Desktop **and** Antigravity (IDE + standalone app)
simultaneously by replacing the single-instance MCP server with a shared daemon
plus thin per-host shims. This removes the single-instance churn where each host
fought over the mic/speaker.

- **`levity_voiced.py`** — one shared daemon that owns the mic / Whisper / TTS.
  Reuses the audio engine from `~/.levity-voice/server.py` (imported as a
  library); adds a Unix-socket IPC server and cross-host coordination (one
  speaker at a time, single mic-capture lock).
- **`levity_shim.py`** — a thin per-host MCP server. Same `voice_*` tools, but
  forwards every call to the daemon. Owns no audio, so many run at once with no
  single-instance churn. Auto-starts (and, on crash, re-starts) the daemon.

## Architecture

```
Claude Desktop ─┐
Antigravity IDE ─┼─► levity_shim.py (one per host) ──unix socket──► levity_voiced.py ──► mic / Whisper / TTS
Antigravity App ─┘        (no audio, just forwards)                  (single shared owner of audio)
```

IPC protocol — one JSON object per line over `~/.levity-voice/voiced.sock`:

```
request : {"op": "speak"|"confirm"|"listen"|"toggle"|"status", ...params}
reply   : {"ok": true, "result": <any>} | {"ok": false, "error": "..."}
```

## Coordination decisions (finalized)

- **Speak policy: interrupt / newest-wins.** A new `speak` cuts off any
  in-flight utterance, serialized by `_speak_lock` so "kill + start" is atomic —
  one voice at a time, never overlapping/garbled audio. Matches single-host
  behavior. A queue was rejected: backlogged speech goes stale in an interactive
  session.
- **Mic capture: single lock.** `confirm`/`listen` take a non-blocking
  `_capture_lock`; if another host already holds the mic the call is **refused**
  (`"Already listening (another host holds the mic)."`) rather than queued, so
  two hosts never open the mic at once.
- **Daemon lifecycle: first-shim-spawns.** The first shim that needs the daemon
  starts it detached (`start_new_session=True`), so it outlives any single host.
  Zero install steps; no launchd agent required. (A launchd agent remains an
  optional future hardening, not needed for correctness.)
- **Crash recovery.** If the daemon is down or dies mid-call, the shim's `_call`
  re-spawns it and retries once. A reply that never fully arrives (daemon
  crashed mid-send) is retried; a request is never silently replayed after a
  partial/garbled reply.
- **Stale-socket reclaim.** On start the daemon probes the existing socket; if
  nothing answers it unlinks the stale file and rebinds. Socket is `0600`
  (user-only).

## Setup (all three hosts)

Each host's MCP config points `levity-voice` at the shim instead of `server.py`:

```jsonc
"levity-voice": {
  "command": "/Users/<you>/.levity-voice/venv/bin/python",
  "args":    ["/Users/<you>/.levity-voice/multi-host/levity_shim.py"]
}
```

Config locations (macOS) and current wiring:

| Host                | Config file                                                        | Wired to    |
| ------------------- | ------------------------------------------------------------------ | ----------- |
| Antigravity (IDE)   | `~/.gemini/antigravity-ide/mcp_config.json`                        | shim ✅     |
| Antigravity (app)   | `~/.gemini/config/mcp_config.json`                                 | shim ✅     |
| Claude Desktop      | `~/Library/Application Support/Claude/claude_desktop_config.json`  | shim ✅     |

All three hosts now run on the shared daemon. Claude Desktop was moved off the
single-instance `server.py` (which suffered recurring MCP crashes from
PortAudio/CoreAudio writing `||PaMacCor` diagnostics to fd 1 — the same fd the
JSON-RPC transport uses) onto the shim. The shim owns no audio, so that stdout
corruption can no longer reach Claude Desktop's transport; the daemon absorbs it
instead. After editing the config, **quit and reopen Claude Desktop** so it
reloads MCP and launches the shim.

The daemon does not need to be started by hand — the first shim call spawns it.
To run it manually for debugging:

```bash
~/.levity-voice/venv/bin/python ~/.levity-voice/multi-host/levity_voiced.py
# logs: ~/.levity-voice/voiced.log   pid: ~/.levity-voice/voiced.pid
```

## Test matrix — all passing

Verified against the live daemon via `/tmp/levity_mh_test.py` (drives the socket
directly, simulating the shims) plus a full MCP stdio handshake against the
shim:

| # | Scenario                                                       | Result |
| - | -------------------------------------------------------------- | ------ |
| 1 | `status` op responds, reports `daemon: true`                   | ✅ pass |
| 2 | Single `speak` routes through daemon                           | ✅ pass |
| 3 | 3 hosts speak concurrently — all accepted, newest-wins (no overlap; in-flight `say` killed via SIGTERM) | ✅ pass |
| 4 | Two concurrent `confirm`/`listen` — mic lock refuses the 2nd   | ✅ pass |
| 5 | `toggle`/`status` round-trips                                  | ✅ pass |
| 6 | Unknown op returns `ok:false` cleanly                          | ✅ pass |
| 7 | Empty `speak` text handled gracefully                          | ✅ pass |
| 8 | Crash recovery: kill daemon → next shim call re-spawns + succeeds | ✅ pass |
| 9 | Single-instance guard: only one daemon ever owns the socket    | ✅ pass |
| 10| Claude Desktop's exact shim invocation initializes as MCP server, exposes all 4 `voice_*` tools, `voice_speak` reaches daemon | ✅ pass |

Note: tests 1–10 validate coordination and routing without live mic hardware.
`voice_confirm`/`voice_listen` recording is bounded by a hard `window` cap in the
engine's `_record_audio` (≤15s confirm, ≤60s listen), so a capture can't hang.
