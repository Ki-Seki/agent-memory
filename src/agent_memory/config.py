import json
import os
import shutil
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROTOCOL = PACKAGE_DIR / "PROTOCOL.md"

# Running from a source checkout (bin/mem, `uv run`, or an editable install) rather than an
# installed package: hooks then call the checkout's bin/mem, so edits take effect at once.
_ROOT = PACKAGE_DIR.parent.parent
CHECKOUT = _ROOT if (_ROOT / "pyproject.toml").is_file() and (_ROOT / "bin" / "mem").is_file() else None
CODE_DIR = CHECKOUT or PACKAGE_DIR

CONFIG_DIR = Path(os.environ.get("AGENT_MEMORY_CONFIG_DIR", "~/.config/agent-memory")).expanduser()
CONFIG_FILE = CONFIG_DIR / "config.json"
PROTOCOL_COPY = CONFIG_DIR / "PROTOCOL.md"  # what Claude Code imports; `mem install` refreshes it


def mem_command():
    """The argv that runs `mem` with this interpreter, for hooks and background sync."""
    if CHECKOUT:
        return [sys.executable, str(CHECKOUT / "bin" / "mem")]
    return [sys.executable, "-m", "agent_memory"]


def _mem_path():
    if CHECKOUT:
        return CHECKOUT / "bin" / "mem"
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
    """The data repository, or None when not configured."""
    value = os.environ.get("AGENT_MEMORY_DATA") or load().get("data_dir")
    return Path(value).expanduser() if value else None
