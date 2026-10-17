"""Made-up memories to try agent-memory with, without installing it or touching your own.

`mem ui --demo` copies them into a temporary data repository whose history has one commit per
memory, the way the hooks write them, and opens the page on it with its own config folder. The
project site's live demo is built from the same memories (scripts/site.py).
"""

import datetime as _dt
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import config, frontmatter, gitsync, install, store

MEMORIES = Path(__file__).with_name("demo") / "memories"
ENV = "AGENT_MEMORY_DEMO"  # set to the demo's temporary folder while a demo runs
DATES = ("created", "updated")


def _when(value):
    try:
        return _dt.datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _shift(meta, days):
    for key in DATES:
        when = _when(meta.get(key))
        if when:
            meta[key] = (when + _dt.timedelta(days=days)).isoformat()


def make(dest, today=None):
    """A data repository at dest holding the demo memories.

    Each memory is committed on its own at the time it was created (and again when it was changed),
    with the subject and trailers the Stop hook writes, so Insights has a history to show. With `today`, every date
    moves by the same number of days so the newest memory is a day old.
    """
    dest = Path(dest)
    mdir = store.memories_dir(dest)
    shutil.copytree(MEMORIES, mdir)
    (dest / ".gitignore").write_text("staging/\n.cache/\n", "utf-8")
    (dest / "README.md").write_text(install.DATA_README, "utf-8")
    files = sorted(mdir.rglob("*.md"))
    docs = {path: frontmatter.split(path.read_text("utf-8")) for path in files}
    if today:
        newest = max(_when(meta.get(k)) for meta, _ in docs.values() for k in DATES if _when(meta.get(k)))
        days = (today - newest.date()).days - 1
        for meta, _ in docs.values():
            _shift(meta, days)

    gitsync.git(dest, "init", "-q", "-b", "main")
    for key, value in {
        "user.name": "agent-memory demo",
        "user.email": "demo@example.com",
        "commit.gpgsign": "false",
    }.items():
        gitsync.git(dest, "config", key, value)

    def commit(paths, when, message):
        gitsync.git(dest, "add", "-A", "--", *[str(p.relative_to(dest)) for p in paths])
        dated = {**os.environ, "GIT_AUTHOR_DATE": when.isoformat(), "GIT_COMMITTER_DATE": when.isoformat()}
        args = ["git", "-C", str(dest), "commit", "-q", "--no-verify", "--allow-empty", "-m", message]
        subprocess.run(args, capture_output=True, text=True, env=dated, check=True)

    first = min(_when(meta["created"]) for meta, _ in docs.values())
    commit([dest / ".gitignore", dest / "README.md"], first - _dt.timedelta(days=1), "Initialize memory repository")
    events = []
    for path, (meta, _) in docs.items():
        events.append((_when(meta["created"]), path, "+1 ~0 -0"))
        if _when(meta.get("updated")):
            events.append((_when(meta["updated"]), path, "+0 ~1 -0"))
    for when, path, counts in sorted(events, key=lambda e: e[0]):
        meta, body = docs[path]
        if counts.startswith("+1") and _when(meta.get("updated")):
            meta = {k: v for k, v in meta.items() if k != "updated"}  # as it was first written
        path.write_text(frontmatter.join(meta, body), "utf-8")
        # the subject and trailers the Stop hook writes (capture.commit)
        src = meta.get("source") or {}
        tool, title = src.get("tool") or "claude-code", src.get("session_name")
        trailers = [f"Tool: {tool}"] + [
            f"{k}: {src[f]}" for k, f in (("Session-Id", "session_id"), ("Host", "host")) if src.get(f)
        ]
        subject = f"memory: {counts} ({tool}: {title})" if title else f"memory: {counts} ({tool})"
        commit([path], when, subject + "\n\n" + "\n".join(trailers))
    return dest


def prepare():
    """A temporary demo: data repository and config folder, named in the environment for `mem ui`."""
    root = Path(tempfile.mkdtemp(prefix="agent-memory-demo-"))
    data, cfg_dir = root / "data", root / "config"
    make(data, today=_dt.date.today())
    cfg_dir.mkdir()
    keep = {k: v for k, v in config.load().items() if k == "embed_model_dir"}  # where the model already is
    (cfg_dir / "config.json").write_text(json.dumps({"data_dir": str(data), **keep}), "utf-8")
    os.environ.update({ENV: str(root), "AGENT_MEMORY_DATA": str(data), "AGENT_MEMORY_CONFIG_DIR": str(cfg_dir)})
    return root
