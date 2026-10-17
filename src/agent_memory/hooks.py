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
from pathlib import Path

from . import capture, config, gitsync, profiles, select, store, workdir
from .context import detect
from .util import log, log_exc

PULL_INTERVAL = 60


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
        profile=profiles.name_of(data_dir),
    )


def flush(payload, tool, data_dir, final):
    sdir = capture.session_dir(data_dir, tool, _session_id(payload))
    if not sdir.is_dir():
        return
    if payload.get("transcript_path"):
        capture.write_session(sdir, {"transcript_path": payload["transcript_path"]})
    committed = capture.flush(data_dir, sdir, final=final, lock_timeout=1.0 if final else 5.0)
    if committed and gitsync.has_remote(data_dir):
        gitsync.spawn_sync(data_dir, push=True)


def _home(payload, tool, active):
    """The data repository holding this session's staging folder: the profile that was active when the
    session started, which need not be the active one now. SessionStart fires again for a running session
    when it compacts or resumes, so that event asks too; a new session has no folder yet and gets `active`."""
    sid = payload.get("session_id")
    for data_dir in profiles.dirs() if sid else []:
        if capture.session_dir(data_dir, tool, str(sid)).is_dir():
            return data_dir
    return active


def main(event, tool):
    payload = _payload()
    data_dir = config.data_dir()
    if data_dir:
        data_dir = _home(payload, tool, data_dir)
    if not data_dir or not (data_dir / ".git").exists():
        return 0
    try:
        if event == "session-start":
            text = session_start(payload, tool, data_dir)
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "SessionStart",
                            "additionalContext": text,
                        }
                    },
                    ensure_ascii=False,
                )
            )
        elif event in ("stop", "session-end"):
            flush(payload, tool, data_dir, final=event == "session-end")
        else:
            log(data_dir, f"unknown hook event {event!r}")
    except Exception:
        log_exc(data_dir, f"hook {event} ({tool})")
    return 0
