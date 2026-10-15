"""Reading memory files from the data repository."""

import json
from pathlib import Path

from . import frontmatter
from .util import SCOPES, TYPES, atomic_write

MEMORIES = "memories"
STAGING = "staging"
CACHE = ".cache"


def memories_dir(data_dir):
    return Path(data_dir) / MEMORIES


def staging_dir(data_dir):
    return Path(data_dir) / STAGING


def first_line(body):
    for line in body.splitlines():
        line = line.strip().lstrip("#").strip()
        if line:
            return line
    return ""


def normalize(meta, body, fallback_id):
    """Fill defaults so callers can rely on the core fields."""
    legacy = meta.get("metadata") if isinstance(meta.get("metadata"), dict) else {}
    typ = str(meta.get("type") or legacy.get("type") or "project").lower()
    scope = str(meta.get("scope") or "here").lower()
    source = meta.get("source") if isinstance(meta.get("source"), dict) else {}
    supersedes = meta.get("supersedes") or []
    if isinstance(supersedes, str):
        supersedes = [s.strip() for s in supersedes.split(",") if s.strip()]
    return {
        "id": str(meta.get("id") or fallback_id),
        "name": str(meta.get("name") or ""),
        "type": typ if typ in TYPES else "project",
        "scope": scope if scope in SCOPES else "here",
        "description": str(meta.get("description") or first_line(body))[:300],
        "created": str(meta.get("created") or ""),
        "updated": str(meta.get("updated") or ""),
        "supersedes": [str(s) for s in supersedes],
        "source": {k: str(v) for k, v in source.items() if v not in (None, "")},
    }


def read(path):
    text = Path(path).read_text("utf-8", errors="replace")
    meta, body = frontmatter.split(text)
    return meta, body


def load_all(data_dir):
    """All memories as normalized dicts with a `rel` path, using an mtime cache."""
    mdir = memories_dir(data_dir)
    cache_file = Path(data_dir) / CACHE / "index.json"
    try:
        cache = json.loads(cache_file.read_text("utf-8"))
    except (OSError, ValueError):
        cache = {}
    fresh, out, dirty = {}, [], False
    for path in sorted(mdir.rglob("*.md")) if mdir.is_dir() else []:
        rel = path.relative_to(mdir).as_posix()
        try:
            st = path.stat()
        except OSError:
            continue
        key = [st.st_mtime_ns, st.st_size]
        entry = cache.get(rel)
        if not entry or entry.get("k") != key:
            try:
                meta, body = read(path)
            except OSError:
                continue
            entry = {"k": key, "m": normalize(meta, body, path.stem)}
            dirty = True
        fresh[rel] = entry
        out.append({**entry["m"], "rel": rel})
    if dirty or len(fresh) != len(cache):
        try:
            atomic_write(cache_file, json.dumps(fresh, ensure_ascii=False))
        except OSError:
            pass
    return out


def find(data_dir, key):
    """Look up a memory by id, name or relative path."""
    for m in load_all(data_dir):
        if key in (m["id"], m["name"], m["rel"]) or m["rel"].endswith("/" + key):
            return m
    return None
