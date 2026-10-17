"""Hook entry points shared by Claude Code and Codex.

Both tools send a JSON payload on stdin with at least `session_id` and `cwd`,
and accept `hookSpecificOutput.additionalContext` from SessionStart hooks.
A hook must never break the host session, so every failure is logged and
swallowed.
"""

import json
import secrets
import sys
import time
from datetime import datetime
from pathlib import Path

from . import capture, config, gitsync, profiles, select, store, workdir
from .context import detect
from .util import log, log_exc

PULL_INTERVAL = 60
SWITCHED = (
    "The active memory profile changed while this session was running. This index replaces the one shown "
    "earlier: from now on use only its memories directory, its staging directory and the memories it lists, "
    "and set aside memories you read under the earlier one.\n\n"
)


def _payload():
    try:
        data = sys.stdin.read()
        return json.loads(data) if data.strip() else {}
    except (OSError, ValueError):
        return {}


def _session_id(payload):
    return str(payload.get("session_id") or f"nosession-{secrets.token_hex(4)}")


def session_start(payload, tool, data_dir):
    sid = _session_id(payload)
    ctx = detect(payload.get("cwd"))
    sdir = capture.session_dir(data_dir, tool, sid)
    sdir.mkdir(parents=True, exist_ok=True)
    capture.write_session(
        sdir,
        {
            "tool": tool,
            "session_id": sid,
            "session_title": payload.get("session_title"),
            "model": payload.get("model"),
            "transcript_path": payload.get("transcript_path"),
            "ctx": ctx,
            "shown_at": time.time(),
        },
    )

    recovered = capture.recover_orphans(data_dir, keep=sdir)
    stamp = Path(data_dir) / ".cache" / "last-pull"
    if gitsync.has_remote(data_dir):
        last = stamp.stat().st_mtime if stamp.exists() else 0
        if recovered or time.time() - last > PULL_INTERVAL:
            stamp.parent.mkdir(parents=True, exist_ok=True)
            stamp.touch()
            gitsync.spawn_sync(data_dir, push=recovered)

    paths = {
        "memories": str(store.memories_dir(data_dir)),
        "staging": str(sdir),
        "mem": str(config.BIN),
    }
    return select.render(
        store.load_all(data_dir),
        ctx,
        paths,
        throwaway=workdir.is_throwaway(ctx.get("cwd")),
        profile=profiles.active_name(),
    )


def _shown(sdir):
    """When this staging folder's profile last gave the session its index; 0 when it never did."""
    info = capture.read_session(sdir)
    if isinstance(info.get("shown_at"), (int, float)):
        return info["shown_at"]
    try:  # sessions that started before shown_at existed got their index when the folder was made
        return datetime.fromisoformat(info["started_at"]).timestamp()
    except (KeyError, TypeError, ValueError):
        return 0


def prompt(payload, tool, data_dir):
    """The active profile's index when the session last got another profile's; None when nothing changed.
    Running sessions follow the active profile, so a switch reaches them with their next message."""
    sid = payload.get("session_id")
    if not sid:
        return None
    seen = [(_shown(sdir), d) for d in profiles.dirs() if (sdir := capture.session_dir(d, tool, str(sid))).is_dir()]
    if not seen or max(seen, key=lambda s: s[0])[1] == data_dir:
        return None  # no index yet (SessionStart gives it), or this profile's is the latest
    return SWITCHED + session_start(payload, tool, data_dir)


def flush(payload, tool, final):
    """Commit what the session staged, into each profile it staged in: a switch can leave some in the one
    before, written while the session still had that profile's index."""
    sid = _session_id(payload)
    for data_dir in profiles.dirs():
        sdir = capture.session_dir(data_dir, tool, sid)
        if not sdir.is_dir() or not (data_dir / ".git").exists():
            continue
        if payload.get("transcript_path"):
            capture.write_session(sdir, {"transcript_path": payload["transcript_path"]})
        committed = capture.flush(data_dir, sdir, final=final, lock_timeout=1.0 if final else 5.0)
        if committed and gitsync.has_remote(data_dir):
            gitsync.spawn_sync(data_dir, push=True)


def _context(event, text):
    return json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}, ensure_ascii=False)


def main(event, tool):
    payload = _payload()
    data_dir = config.data_dir()  # the active profile's: running sessions follow it too
    if not data_dir or not (data_dir / ".git").exists():
        return 0
    try:
        if event == "session-start":
            print(_context("SessionStart", session_start(payload, tool, data_dir)))
        elif event == "prompt":
            text = prompt(payload, tool, data_dir)
            if text:
                print(_context("UserPromptSubmit", text))
        elif event in ("stop", "session-end"):
            flush(payload, tool, final=event == "session-end")
        else:
            log(data_dir, f"unknown hook event {event!r}")
    except Exception:
        log_exc(data_dir, f"hook {event} ({tool})")
    return 0
