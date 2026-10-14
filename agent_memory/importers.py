"""One-off import of the native Claude Code and Codex memories.

Native files are only read, never modified. Re-running an import skips
memories that were already imported (matched on `source.original`).
"""

import json
import os
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from . import frontmatter, gitsync, sessions
from .context import detect
from .store import load_all, memories_dir, normalize, read
from .util import HOME, atomic_write, id_path, new_id, now, parse_time, slugify

CLAUDE_PROJECTS = Path(os.environ.get("CLAUDE_CONFIG_DIR", HOME / ".claude")) / "projects"
CODEX_MEMORIES = Path(os.environ.get("CODEX_HOME", HOME / ".codex")) / "memories"
ADHOC_TAG = "[ad-hoc note]"


def _git_source(cwd):
    if not cwd:
        return {}
    ctx = detect(cwd) if os.path.isdir(cwd) else {"cwd": cwd, "host": detect(HOME)["host"]}
    ctx.pop("git_commit", None)  # the commit at import time says nothing about the memory
    return ctx


def _record(*, name, typ, scope, description, body, created, source):
    when = parse_time(created) or now()
    memory_id = new_id(name, when)
    meta = {"id": memory_id, "name": slugify(name), "type": typ, "scope": scope,
            "description": " ".join(description.split())[:300], "created": when.isoformat(),
            "source": {k: v for k, v in source.items() if v}}
    return memory_id, meta, body


# ---------------------------------------------------------------- Claude Code

def _decode_project_dir(name):
    """Recover a folder from Claude's dash-encoded project dir name, if it still exists."""
    tokens = name.lstrip("-").split("-")

    @lru_cache(maxsize=None)
    def entries(base):
        try:
            return tuple(os.listdir(base))
        except OSError:
            return ()

    def walk(i, base, comp):
        if i == len(tokens):
            return str(base / comp) if (base / comp).exists() else None
        tok = tokens[i]
        if (base / comp).is_dir():
            hit = walk(i + 1, base / comp, tok)
            if hit:
                return hit
        for sep in ("-", ".", "_", " "):
            longer = comp + sep + tok
            if any(e.startswith(longer) for e in entries(base)):
                hit = walk(i + 1, base, longer)
                if hit:
                    return hit
        return None

    return walk(1, Path("/"), tokens[0]) if tokens else None


def _transcript_cwd(project_dir, session_id):
    candidates = []
    if session_id:
        candidates.append(project_dir / f"{session_id}.jsonl")
    candidates += sorted(project_dir.glob("*.jsonl"))
    for path in candidates:
        if not path.exists():
            continue
        try:
            with path.open(encoding="utf-8", errors="replace") as f:
                for raw in f:
                    if '"cwd"' in raw:
                        cwd = json.loads(raw).get("cwd")
                        if cwd:
                            return cwd, path
        except (OSError, ValueError):
            continue
    return None, None


def _infer_workdir(transcript):
    """Most-referenced existing project folder in a transcript, for scratch sessions.

    Sessions started without a project folder still work on real repositories
    through absolute paths; the folder they touch most is where the memory belongs.
    """
    pattern = re.compile(re.escape(str(HOME)) + r"/(?:repos|Documents|Library/CloudStorage/[^/\"\\]+)"
                         r"/[^/\"\\\s]+")
    counts = {}
    try:
        with open(transcript, encoding="utf-8", errors="replace") as f:
            for raw in f:
                for hit in pattern.findall(raw):
                    counts[hit] = counts.get(hit, 0) + 1
    except OSError:
        return None
    for path, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        if n >= 3 and os.path.isdir(path) and "scratch-workspaces" not in path:
            return path
    return None


def claude_items():
    for mem_dir in sorted(CLAUDE_PROJECTS.glob("*/memory")):
        project_dir = mem_dir.parent
        for path in sorted(mem_dir.glob("*.md")):
            if path.name == "MEMORY.md":
                continue
            meta, body = read(path)
            legacy = meta.get("metadata") if isinstance(meta.get("metadata"), dict) else {}
            m = normalize(meta, body, path.stem)
            origin = legacy.get("originSessionId") or meta.get("originSessionId")
            cwd, transcript = _transcript_cwd(project_dir, origin)
            cwd = cwd or _decode_project_dir(project_dir.name)
            original_cwd = None
            if cwd and "/scratch-workspaces/" in cwd and transcript:
                inferred = _infer_workdir(transcript)
                if inferred:
                    original_cwd, cwd = cwd, inferred
            created = legacy.get("modified") or meta.get("modified") or _mtime(path)
            title = sessions.title("claude-code", origin, transcript) if transcript else ""
            source = {"tool": "claude-code", "session_id": origin, "session_name": title,
                      **_git_source(cwd),
                      "original_cwd": original_cwd,
                      "imported_from": "claude-code auto memory",
                      "original": "~/" + path.relative_to(HOME).as_posix()}
            yield _record(name=m["name"] or path.stem, typ=m["type"],
                          scope="global" if m["type"] in ("user", "feedback") else "here",
                          description=m["description"], body=body, created=created,
                          source=source)


def _mtime(path):
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat()


# ---------------------------------------------------------------- Codex

def _sections(text):
    out, current = {}, None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            out[current] = []
        elif current:
            out[current].append(line)
    return out


def _bullets(lines):
    items, cur = [], None
    for line in lines:
        if line.startswith("- "):
            cur = [line[2:].strip()]
            items.append(cur)
        elif cur is not None and line.startswith("  ") and line.strip():
            cur.append(line.strip())
        else:
            cur = None
    return [" ".join(i) for i in items]


def _codex_source(original, cwd=None, thread=None):
    title = sessions.title("codex", thread) if thread else ""
    return {"tool": "codex", "session_id": thread, "session_name": title,
            **_git_source(cwd), "imported_from": "codex memories",
            "original": "~/" + (CODEX_MEMORIES / original).relative_to(HOME).as_posix()}


def codex_items():
    summary = CODEX_MEMORIES / "memory_summary.md"
    if summary.exists():
        sec = _sections(summary.read_text("utf-8"))
        created = _mtime(summary)
        profile = " ".join(l.strip() for l in sec.get("User Profile", []) if l.strip())
        if profile:
            profile = profile.replace(ADHOC_TAG, "").strip()
            yield _record(name="user-profile-from-codex", typ="user", scope="global",
                          description="User profile as summarised by Codex: " + profile[:200],
                          body=profile + "\n", created=created,
                          source=_codex_source("memory_summary.md#user-profile"))
        for heading in ("User preferences", "General Tips"):
            for n, text in enumerate(_bullets(sec.get(heading, []))):
                if ADHOC_TAG in text or text.startswith("Skills:"):
                    continue  # ad-hoc notes are imported from their own files
                yield _record(name=" ".join(text.split()[:6]), typ="feedback", scope="global",
                              description=text, body=text + "\n", created=created,
                              source=_codex_source(f"memory_summary.md#{slugify(heading)}-{n}"))

    handbook = CODEX_MEMORIES / "MEMORY.md"
    if handbook.exists():
        blocks = re.split(r"(?m)^(?=# Task Group: )", handbook.read_text("utf-8"))
        for block in blocks:
            if not block.startswith("# Task Group: "):
                continue
            title = block.splitlines()[0][len("# Task Group: "):].strip()
            cwd = next(iter(re.findall(r"cwd=([^\s;,)]+)", block)), None)
            thread = next(iter(re.findall(r"thread_id=([0-9a-f-]{36})", block)), None)
            stamps = sorted(re.findall(r"updated_at=([0-9T:.+-]+Z?)", block))
            yield _record(name=title, typ="project", scope="here",
                          description=f"Codex task history: {title}", body=block.rstrip() + "\n",
                          created=stamps[-1] if stamps else _mtime(handbook),
                          source=_codex_source(f"MEMORY.md#{slugify(title)}", cwd, thread))

    for path in sorted((CODEX_MEMORIES / "extensions" / "ad_hoc" / "notes").glob("*.md")):
        body = path.read_text("utf-8")
        _, raw = frontmatter.split(body)
        desc = normalize({}, raw, path.stem)["description"]
        name = re.sub(r"^[0-9T_-]+", "", path.stem) or path.stem
        yield _record(name=name, typ="reference", scope="global", description=desc, body=raw,
                      created=_mtime(path),
                      source=_codex_source(path.relative_to(CODEX_MEMORIES).as_posix()))


# ---------------------------------------------------------------- driver

def run(which, data_dir, dry_run=False):
    items = list(claude_items() if which == "claude" else codex_items())
    seen = {m["source"].get("original") for m in load_all(data_dir)}
    fresh = [it for it in items if it[1]["source"].get("original") not in seen]
    for _, meta, _ in fresh:
        src = meta["source"]
        where = src.get("git_remote") or src.get("cwd") or "-"
        print(f"{meta['type']:<9} {meta['scope']:<6} {meta['description'][:70]:<70}  {where}")
    print(f"\n{len(fresh)} to import, {len(items) - len(fresh)} already imported")
    if dry_run or not fresh:
        return
    with gitsync.Lock(data_dir, timeout=30) as locked:
        if not locked:
            raise SystemExit("lock busy")
        for memory_id, meta, body in fresh:
            atomic_write(memories_dir(data_dir) / id_path(memory_id), frontmatter.join(meta, body))
        label = "claude-code auto memory" if which == "claude" else "codex memories"
        gitsync.commit(data_dir, f"import: {len(fresh)} memories from {label}\n\nTool: import")
    print("imported and committed")
