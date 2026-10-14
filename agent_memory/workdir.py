"""Finding the real project folder behind a throwaway session folder.

Claude Code sessions started without a folder run in a scratch workspace, and
the Codex desktop app creates a fresh folder per thread. A `here` memory
recorded there would never match a later session, so we look at the session
transcript and attribute the memory to the folder the session worked in most.
"""

import json
import os
import re
from pathlib import Path

from . import config
from .util import HOME, is_under

DEFAULT_THROWAWAY = [
    r"/scratch-workspaces/",                          # Claude Code, no folder chosen
    r"^~/Documents/Codex/\d{4}-\d{2}-\d{2}/[^/]+",    # Codex desktop, one folder per thread
]
# Folders that only hold other folders; never the answer on their own.
CONTAINERS = re.compile(r"^(Library/CloudStorage(/[^/]+)?|Library/Application Support|"
                        r"Library/Mobile Documents|Documents|Documents/Codex|Desktop|Downloads)$")
TAIL_BYTES = 8 * 1024 * 1024  # new memories are about recent work
MIN_HITS = 3
DESCEND_SHARE = 0.6
MAX_DEPTH = 4  # levels below home; a git root always ends the descent


def _patterns(home):
    pats = config.load().get("throwaway_patterns") or DEFAULT_THROWAWAY
    return [re.compile(p.replace("^~", "^" + re.escape(str(home)), 1)) for p in pats]


def is_throwaway(path, home=None):
    return bool(path) and any(p.search(path) for p in _patterns(home or HOME))


# Under ~/Library only synced document folders can hold projects.
LIBRARY_PROJECT_ROOTS = ("CloudStorage", "Mobile Documents")


def _evidence(line):
    """True for transcript lines that show what the session did.

    Instructions and injected context (AGENTS.md, CLAUDE.md, memory summaries,
    hook output) mention many unrelated folders, so only tool calls, tool
    results and the conversation itself count.
    """
    try:
        d = json.loads(line)
    except ValueError:
        return False
    kind = d.get("type")
    if kind == "response_item":  # Codex rollout
        payload = d.get("payload") or {}
        return payload.get("type") != "message" or payload.get("role") == "assistant"
    return kind in ("user", "assistant")  # Claude Code transcript


def _read_evidence(path):
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            if size > TAIL_BYTES:
                f.seek(size - TAIL_BYTES)
            raw = f.read().decode("utf-8", "replace")
    except (OSError, TypeError):
        return ""
    return "\n".join(line for line in raw.splitlines() if _evidence(line))


def infer(transcript, cwd=None, exclude=(), home=None):
    """The project folder a transcript refers to most, or None.

    Counts every folder prefix (two to five levels below home) of the absolute
    paths in the transcript, starts from the most referenced top-level folder,
    and descends while one child holds most of the references, stopping at a
    git checkout root.
    """
    home = Path(home or HOME)
    text = _read_evidence(transcript) if transcript else ""
    if not text:
        return None
    path_re = re.compile(re.escape(str(home)) + r"(?:/[^\s\"'\\`<>|;:,()\[\]{}*?]+)+")
    counts = {}
    for m in path_re.finditer(text):
        parts = Path(m.group(0).rstrip(".")).relative_to(home).parts
        if len(parts) < 2 or parts[0].startswith("."):
            continue
        if parts[0] == "Library" and parts[1] not in LIBRARY_PROJECT_ROOTS:
            continue
        for depth in range(2, min(len(parts), 5) + 1):
            key = parts[:depth]
            counts[key] = counts.get(key, 0) + 1

    blocked = [str(Path(e)) for e in exclude if e]

    def usable(key):
        p = str(home.joinpath(*key))
        if not os.path.isdir(p) or is_throwaway(p, home):
            return False
        if cwd and (p == cwd or is_under(cwd, p)):
            return False
        return not any(p == b or is_under(p, b) for b in blocked)

    top = [(n, k) for k, n in counts.items() if len(k) == 2 and usable(k)]
    if not top:
        return None
    n, best = max(top)
    if n < MIN_HITS:
        return None
    limit = MAX_DEPTH + (2 if best[0] == "Library" else 0)  # ~/Library/CloudStorage/<drive>/...
    while len(best) < limit and not home.joinpath(*best, ".git").exists():
        kids = [(c, k) for k, c in counts.items()
                if len(k) == len(best) + 1 and k[:len(best)] == best and usable(k)]
        if not kids:
            break
        c, k = max(kids)
        if c < DESCEND_SHARE * n and not CONTAINERS.match("/".join(best)):
            break
        n, best = c, k
    if CONTAINERS.match("/".join(best)):
        return None
    return str(home.joinpath(*best))


def default_exclude():
    data = config.data_dir()
    return [str(config.CODE_DIR)] + ([str(data)] if data else [])
