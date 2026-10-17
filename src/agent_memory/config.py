import json
import os
import shutil
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROTOCOL = PACKAGE_DIR / "PROTOCOL.md"

CODE_DIR = PACKAGE_DIR

CONFIG_DIR = Path(os.environ.get("AGENT_MEMORY_CONFIG_DIR", "~/.config/agent-memory")).expanduser()
CONFIG_FILE = CONFIG_DIR / "config.json"
PROTOCOL_COPY = CONFIG_DIR / "PROTOCOL.md"  # what Claude Code imports; `mem install` refreshes it


def _python():
    """This interpreter, as the `python` beside it when that is the same file. Whether `mem` was
    started as python3 or python3.11 (uv has changed its entry scripts) then leaves the hook
    commands alone, so `mem install` does not rewrite them and Codex does not ask to trust them again."""
    exe = Path(sys.executable)
    try:
        plain = exe.with_name("python")
        return str(plain) if plain != exe and plain.samefile(exe) else sys.executable
    except (OSError, ValueError):  # no `python` beside it, or no sys.executable at all
        return sys.executable


def mem_command():
    """The argv that runs `mem` with this interpreter, for hooks and background sync."""
    return [_python(), "-m", "agent_memory"]


def _mem_path():
    found = shutil.which("mem")
    return Path(found) if found else Path(sys.executable).with_name("mem")


BIN = _mem_path()  # the `mem` executable agents are told to use


def load():
    try:
        return json.loads(CONFIG_FILE.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def save(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", "utf-8")


def data_dir():
    """The data repository: AGENT_MEMORY_DATA when set, else the active profile's folder; None when not configured."""
    value = os.environ.get("AGENT_MEMORY_DATA")
    if not value:
        cfg = load()
        profiles = cfg.get("profiles") if isinstance(cfg.get("profiles"), dict) else {}
        value = (profiles.get(cfg.get("profile")) or {}).get("data_dir") or cfg.get("data_dir")
    return Path(value).expanduser() if value else None
