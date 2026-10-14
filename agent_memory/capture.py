"""Turning files an agent wrote into staging into committed memories."""

import json
import shutil
import time
from pathlib import Path

from . import frontmatter, gitsync, sessions, workdir
from .context import detect
from .store import memories_dir, normalize, read, staging_dir
from .util import atomic_write, id_path, log, new_id, now, now_iso

SESSION_FILE = ".session.json"
ORPHAN_AGE = 6 * 3600
STALE_AGE = 3 * 86400


def session_dir(data_dir, tool, session_id):
    return staging_dir(data_dir) / f"{tool}-{session_id}"


def write_session(sdir, info):
    path = Path(sdir) / SESSION_FILE
    try:
        old = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        old = {}
    merged = {**old, **{k: v for k, v in info.items() if v}}
    merged.setdefault("started_at", now_iso())
    atomic_write(path, json.dumps(merged, ensure_ascii=False, indent=2))
    return merged


def read_session(sdir):
    try:
        return json.loads((Path(sdir) / SESSION_FILE).read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def relocate(ctx, transcript):
    """Point a throwaway folder at the project the session worked in, if any."""
    cwd = ctx.get("cwd")
    if not workdir.is_throwaway(cwd):
        return ctx
    inferred = workdir.infer(transcript, cwd, workdir.default_exclude())
    if not inferred:
        return ctx
    moved = detect(inferred)
    moved.pop("git_commit", None)  # HEAD now may differ from what the session saw
    return {**moved, "host": ctx.get("host", moved.get("host")), "original_cwd": cwd}


def _source(session):
    tool, sid = session.get("tool"), session.get("session_id")
    transcript = session.get("transcript_path") or sessions.transcript_path(tool, sid)
    ctx = relocate(session.get("ctx") or {}, transcript)
    title = sessions.title(tool, sid, transcript) or session.get("session_title", "")
    src = {
        "tool": tool,
        "session_id": sid,
        "session_name": title,
        "model": session.get("model"),
        "host": ctx.get("host"),
        "cwd": ctx.get("cwd"),
        "original_cwd": ctx.get("original_cwd"),
        "git_root": ctx.get("git_root"),
        "git_remote": ctx.get("git_remote"),
        "git_branch": ctx.get("git_branch"),
        "git_commit": ctx.get("git_commit"),
        "transcript": transcript,
    }
    return {k: v for k, v in src.items() if v}


def _delete_ids(data_dir, ids):
    if not ids:
        return 0
    wanted, removed = set(ids), 0
    for path in memories_dir(data_dir).rglob("*.md"):
        if path.stem in wanted:
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def promote(data_dir, sdir, session=None):
    """Move staged *.md files into memories/ with ids and provenance. Returns count."""
    sdir = Path(sdir)
    staged = sorted(p for p in sdir.glob("*.md") if p.is_file())
    if not staged:
        return 0
    session = session or read_session(sdir)
    source = _source(session)
    count = 0
    for path in staged:
        try:
            meta, body = read(path)
        except OSError:
            continue
        if not body.strip() and not meta:
            path.unlink(missing_ok=True)
            continue
        m = normalize(meta, body, path.stem)
        when = now()
        name = m["name"] or path.stem
        memory_id = new_id(name, when)
        out = {
            "id": memory_id,
            "name": name,
            "type": m["type"],
            "scope": m["scope"],
            "description": m["description"],
            "created": when.isoformat(),
        }
        if m["supersedes"]:
            out["supersedes"] = m["supersedes"]
        out["source"] = source
        target = memories_dir(data_dir) / id_path(memory_id)
        atomic_write(target, frontmatter.join(out, body))
        path.unlink(missing_ok=True)
        _delete_ids(data_dir, m["supersedes"])
        count += 1
    return count


def stamp_updates(data_dir):
    """Set `updated` on tracked memory files that were edited in place."""
    r = gitsync.git(data_dir, "status", "--porcelain", "-z", "--", "memories")
    if r.returncode != 0:
        return 0
    stamped = 0
    for entry in r.stdout.split("\0"):
        if len(entry) < 4 or entry[:2].strip() not in ("M", "MM"):
            continue
        path = Path(data_dir) / entry[3:]
        try:
            meta, body = read(path)
        except OSError:
            continue
        if not meta.get("id"):
            continue
        meta["updated"] = now_iso()
        atomic_write(path, frontmatter.join(meta, body))
        stamped += 1
    return stamped


def commit(data_dir, session, label=""):
    stamp_updates(data_dir)
    title = sessions.title(session.get("tool"), session.get("session_id"),
                           session.get("transcript_path")) or session.get("session_title", "")
    stat = gitsync.git(data_dir, "status", "--porcelain", "-uall", "--",
                       "memories").stdout.splitlines()
    added = sum(1 for s in stat if s.startswith("??") or s.startswith("A"))
    deleted = sum(1 for s in stat if s[:2].strip() == "D")
    changed = len(stat) - added - deleted
    subject = f"memory: +{added} ~{changed} -{deleted}"
    who = session.get("tool") or label or "manual"
    subject += f" ({who}: {title})" if title else f" ({who})"
    trailers = [f"Tool: {who}"]
    if session.get("session_id"):
        trailers.append(f"Session-Id: {session['session_id']}")
    host = (session.get("ctx") or {}).get("host")
    if host:
        trailers.append(f"Host: {host}")
    return gitsync.commit(data_dir, subject + "\n\n" + "\n".join(trailers))


def flush(data_dir, sdir, final=False, lock_timeout=5.0):
    """Promote one session's staging dir and commit. Returns True if committed."""
    with gitsync.Lock(data_dir, lock_timeout) as locked:
        if not locked:
            log(data_dir, f"flush skipped, lock busy: {sdir}")
            return False
        session = read_session(sdir)
        n = promote(data_dir, sdir, session)
        committed = commit(data_dir, session)
        if final and Path(sdir).is_dir() and not any(Path(sdir).glob("*.md")):
            shutil.rmtree(sdir, ignore_errors=True)
        if n or committed:
            log(data_dir, f"flush {Path(sdir).name}: promoted={n} committed={committed}")
        return committed


def recover_orphans(data_dir, keep=None):
    """Promote staging dirs left by sessions that ended without a final flush."""
    root = staging_dir(data_dir)
    if not root.is_dir():
        return False
    committed = False
    for sdir in root.iterdir():
        if not sdir.is_dir() or (keep and sdir == Path(keep)):
            continue
        marker = sdir / SESSION_FILE
        age = time.time() - (marker.stat().st_mtime if marker.exists() else sdir.stat().st_mtime)
        has_files = any(sdir.glob("*.md"))
        if has_files and age > ORPHAN_AGE:
            committed |= flush(data_dir, sdir, final=True, lock_timeout=1.0)
        elif not has_files and age > STALE_AGE:
            shutil.rmtree(sdir, ignore_errors=True)
    return committed


def manual_session(cwd=None):
    """Session info for memories added from the command line."""
    return {"tool": "cli", "ctx": detect(cwd)}
