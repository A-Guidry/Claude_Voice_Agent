#!/usr/bin/env python3
"""
levity-shim — thin per-host MCP server.

Each host (Claude Desktop, Antigravity IDE, Antigravity.app) runs its own copy
of this shim. It exposes the same voice tools but does NO audio itself — every
call is forwarded to the shared daemon (levity_voiced.py) over a Unix socket.
Because the shim owns no mic/speaker, many shims run at once with no contention
(this is what removes the single-instance churn).

If the daemon isn't running, the shim starts it, then connects. If the daemon
dies mid-session, _call re-spawns it and retries once (crash recovery).
"""

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

CONFIG_DIR = Path.home() / ".levity-voice"
SOCKET_PATH = CONFIG_DIR / "voiced.sock"
DAEMON = Path(__file__).resolve().parent / "levity_voiced.py"


def _ensure_daemon() -> None:
    """Start the daemon if its socket isn't accepting connections."""
    if _try_connect() is not None:
        return
    try:
        log = open(CONFIG_DIR / "voiced.log", "a")  # capture daemon output for debugging
    except OSError:
        log = subprocess.DEVNULL
    try:
        subprocess.Popen(
            [sys.executable, str(DAEMON)],
            stdout=log, stderr=log,
            start_new_session=True,
        )
    except OSError:
        return
    for _ in range(50):  # wait up to ~5s for the socket
        time.sleep(0.1)
        if _try_connect() is not None:
            return


def _try_connect():
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(str(SOCKET_PATH))
        return s
    except OSError:
        return None


def _call(req: dict, timeout: float = 90.0):
    """Send one request to the daemon and return its parsed result.

    Crash recovery: if the daemon is down or dies mid-call, re-spawn it and
    retry once. A connection that drops before any reply bytes arrive (daemon
    crashed) is treated as retryable; a partial/garbled reply is not (the
    request may have had a side effect, so we don't replay it).
    """
    last_err = "voice daemon unavailable"
    for attempt in range(2):
        _ensure_daemon()
        s = _try_connect()
        if s is None:
            last_err = "voice daemon unavailable"
            continue  # daemon didn't come up; _ensure_daemon will re-spawn
        try:
            s.settimeout(timeout)
            s.sendall((json.dumps(req) + "\n").encode("utf-8"))
            buf = b""
            while b"\n" not in buf:
                chunk = s.recv(4096)
                if not chunk:
                    break
                buf += chunk
            if b"\n" not in buf:
                # Connection closed before a full reply — daemon likely crashed.
                last_err = "voice daemon closed connection"
                continue
            return json.loads(buf.split(b"\n", 1)[0].decode("utf-8"))
        except (ConnectionError, socket.timeout, OSError) as exc:
            last_err = repr(exc)
            continue  # transport-level failure: retry against a fresh daemon
        except Exception as exc:
            return {"ok": False, "error": repr(exc)}
        finally:
            s.close()
    return {"ok": False, "error": last_err}


mcp = FastMCP(
    "levity_voice",
    instructions=(
        "MANDATORY: call voice_speak at the end of EVERY response so the user "
        "hears it. Use voice_confirm for yes/no approvals and voice_listen for "
        "free-form answers; ask with voice_speak first. (Routed through the "
        "shared Levity voice daemon.)"
    ),
)


@mcp.tool(name="voice_speak")
async def voice_speak(text: str, force_local: bool = False) -> str:
    """Speak text aloud to the user (routed through the shared Levity daemon).

    MANDATORY: call this at the END of EVERY response so the user hears it. The
    user interacts hands-free and relies on spoken output. If the reply is long
    or contains code, pass a short, natural spoken summary rather than the full
    text. Returns immediately; audio plays in the background.

    Args:
        text: The text to speak aloud.
        force_local: If True, always use the local system voice.
    """
    r = _call({"op": "speak", "text": text, "force_local": force_local})
    return r.get("result") if r.get("ok") else f"Error: {r.get('error')}"


@mcp.tool(name="voice_confirm")
async def voice_confirm(timeout_seconds: float = 5.0) -> str:
    """Ask the user for a quick spoken yes/no and return their decision.

    Use before any action needing approval ("Should I proceed?"). First call
    voice_speak to ASK aloud, then voice_confirm to capture the answer. Returns
    JSON {"decision": "yes"|"no"|"unclear", "transcript": "..."}. Only proceed
    on "yes"; treat "no"/"unclear" as do-not-proceed.

    Args:
        timeout_seconds: Max seconds to listen (2-15).
    """
    r = _call({"op": "confirm", "timeout": timeout_seconds})
    if not r.get("ok"):
        return json.dumps({"decision": "unclear", "transcript": "", "error": r.get("error")})
    return json.dumps(r["result"])


@mcp.tool(name="voice_listen")
async def voice_listen(timeout_seconds: float = 30.0) -> str:
    """Listen for a full, free-form spoken reply and return the transcript.

    The open-ended counterpart to voice_confirm — use for open questions
    ("Which option?", "What should I name it?"). First voice_speak the question,
    then voice_listen. Returns the transcribed text or "(no speech detected)".

    Args:
        timeout_seconds: Max seconds to listen (3-60).
    """
    r = _call({"op": "listen", "timeout": timeout_seconds})
    return r.get("result") if r.get("ok") else f"Error: {r.get('error')}"


@mcp.tool(name="voice_toggle")
async def voice_toggle(action: str) -> str:
    """Control the voice service. Actions: start, stop, response_on,
    response_off, mode_quick, mode_full, status. Call once with "start" to
    activate the voice service, then speak every reply with voice_speak.

    Args:
        action: One of the actions above.
    """
    r = _call({"op": "status" if action.strip().lower() == "status" else "toggle",
               "action": action})
    res = r.get("result") if r.get("ok") else {"error": r.get("error")}
    return json.dumps(res) if isinstance(res, dict) else str(res)


if __name__ == "__main__":
    mcp.run()
