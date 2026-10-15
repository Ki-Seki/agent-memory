"""Best-effort lookup of a session's human-readable name."""

import json
import os
import sqlite3
from pathlib import Path


def _claude_title(transcript):
    title = ""
    try:
        with open(transcript, encoding="utf-8", errors="replace") as f:
            for raw in f:
                if '"custom-title"' not in raw:
                    continue
                try:
                    title = json.loads(raw).get("customTitle") or title
                except ValueError:
                    pass
    except OSError:
        pass
    return title


def _codex_thread(session_id, column):
    home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    dbs = sorted(home.glob("state_*.sqlite"))
    if not dbs or not session_id:
        return ""
    try:
        con = sqlite3.connect(f"file:{dbs[-1]}?mode=ro", uri=True, timeout=1)
        try:
            row = con.execute(f"select {column} from threads where id = ?", (session_id,)).fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return ""
    return (row[0] or "") if row else ""


def _codex_title(session_id):
    return _codex_thread(session_id, "coalesce(nullif(name, ''), title)")


def transcript_path(tool, session_id):
    """Locate a session transcript when the hook payload did not carry one."""
    if not session_id:
        return ""
    if tool == "codex":
        return _codex_thread(session_id, "rollout_path")
    claude = Path(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude")).expanduser()
    hits = list(claude.glob(f"projects/*/{session_id}.jsonl"))
    return str(hits[0]) if hits else ""


def title(tool, session_id, transcript=None):
    if tool == "codex":
        name = _codex_title(session_id)
    elif transcript:
        name = _claude_title(transcript)
    else:
        name = ""
    return " ".join(str(name).split())[:120]
