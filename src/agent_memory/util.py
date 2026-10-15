import datetime as _dt
import os
import re
import secrets
import tempfile
import traceback
from pathlib import Path

HOME = Path.home()

TYPES = ("user", "feedback", "project", "reference")
SCOPES = ("global", "here")

_B32 = "0123456789abcdefghjkmnpqrstvwxyz"


def now():
    return _dt.datetime.now().astimezone().replace(microsecond=0)


def now_iso():
    return now().isoformat()


def parse_time(value):
    """Best-effort ISO 8601 parse; returns an aware datetime or None."""
    if not value:
        return None
    s = str(value).strip().replace("Z", "+00:00")
    try:
        t = _dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return t if t.tzinfo else t.astimezone()


def slugify(text, limit=40):
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    s = s[:limit].rstrip("-")
    return s or "note"


def new_id(slug, when=None):
    when = when or now()
    suffix = "".join(_B32[b % 32] for b in secrets.token_bytes(4))
    return f"{when:%Y%m%d}-{slugify(slug)}-{suffix}"


def id_path(memory_id):
    """Relative path of a memory inside the memories directory."""
    return f"{memory_id[:4]}/{memory_id[4:6]}/{memory_id}.md"


def is_under(child, parent):
    try:
        return os.path.commonpath([child, parent]) == parent and child != parent
    except ValueError:
        return False


def specific(path):
    """True if a folder is narrow enough to share memories with its relatives.

    Home, the filesystem root and direct children of home (like ~/repos) are
    too broad: matching on them would leak memories across unrelated work.
    """
    if not path:
        return False
    p = Path(path)
    home = HOME
    if p == home or p == Path(p.anchor):
        return False
    try:
        return len(p.relative_to(home).parts) >= 2
    except ValueError:
        return len(p.parts) >= 4


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def log(data_dir, message):
    try:
        path = Path(data_dir) / ".cache" / "agent-memory.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > 1_000_000:
            path.replace(path.with_suffix(".log.1"))
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{now_iso()} {message}\n")
    except OSError:
        pass


def log_exc(data_dir, where):
    log(data_dir, f"ERROR in {where}:\n{traceback.format_exc()}")
