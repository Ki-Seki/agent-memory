"""Made-up memories to try agent-memory with, without installing it or touching your own.

There are two profiles of them, one for work and one for home. `mem ui --demo` copies each into a temporary data
repository whose history has one commit per memory, the way the hooks write them, and opens the page on
them with a config folder of its own. The project site's live demo is built from the same memories
(scripts/site.py).
"""

import datetime as _dt
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import config, frontmatter, gitsync, install, store

DEMO = Path(__file__).with_name("demo")
# the demo's profiles, the active one first, named as profiles.new_name would; each one's memories are in demo/<id>
PROFILES = {
    "work": {"name": "Quiet Harbor", "folder": "agent-memory-data"},
    "personal": {"name": "Sunny Orchard", "folder": "agent-memory-personal"},
}
ENV = "AGENT_MEMORY_DEMO"  # set to the demo's temporary folder while a demo runs
DATES = ("created", "updated")


def memories(profile):
    return DEMO / profile


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


def _newest():
    """When the newest demo memory, in any profile, was written or changed."""
    stamps = []
    for path in DEMO.rglob("*.md"):
        meta, _ = frontmatter.split(path.read_text("utf-8"))
        stamps += [_when(meta.get(k)) for k in DATES if _when(meta.get(k))]
    return max(stamps)


def make(dest, today=None, profile="work"):
    """A data repository at dest holding one profile's demo memories.

    Each memory is committed on its own at the time it was created (and again when it was changed),
    with the subject and trailers the Stop hook writes, so Insights has a history to show. With `today`, every date
    moves by the same number of days so the newest memory of all the profiles is a day old.
    """
    dest = Path(dest)
    mdir = store.memories_dir(dest)
    shutil.copytree(memories(profile), mdir)
    (dest / ".gitignore").write_text("staging/\n.cache/\n", "utf-8")
    (dest / "README.md").write_text(install.DATA_README, "utf-8")
    files = sorted(mdir.rglob("*.md"))
    docs = {path: frontmatter.split(path.read_text("utf-8")) for path in files}
    if today:
        days = (today - _newest().date()).days - 1
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
    """A temporary demo: a data repository per profile and a config folder, named in the environment for `mem ui`.

    Profiles work in it as they do in yours, except that new ones have to stay in its temporary folder.
    """
    root = Path(tempfile.mkdtemp(prefix="agent-memory-demo-"))
    cfg_dir = root / "config"
    profiles = {}
    for pid, p in PROFILES.items():
        data = root / p["folder"]
        make(data, today=_dt.date.today(), profile=pid)
        profiles[pid] = {"name": p["name"], "data_dir": str(data)}
    cfg_dir.mkdir()
    keep = {k: v for k, v in config.load().items() if k == "embed_model_dir"}  # where the model already is
    active = next(iter(profiles))
    cfg = {"data_dir": profiles[active]["data_dir"], "profiles": profiles, "profile": active, **keep}
    (cfg_dir / "config.json").write_text(json.dumps(cfg, ensure_ascii=False), "utf-8")
    os.environ.pop("AGENT_MEMORY_DATA", None)  # the profiles pick the folder
    os.environ.update({ENV: str(root), "AGENT_MEMORY_CONFIG_DIR": str(cfg_dir)})
    return root


def fingerprint():
    """A hash of the demo memories, so the site's saved demo data can tell when they change."""
    h = hashlib.sha256()
    for path in sorted(DEMO.rglob("*.md")):
        h.update(str(path.relative_to(DEMO)).encode() + b"\0" + path.read_bytes() + b"\0")
    return h.hexdigest()[:16]
