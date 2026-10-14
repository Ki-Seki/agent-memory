import json
import os
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent.parent
BIN = CODE_DIR / "bin" / "mem"
PROTOCOL = CODE_DIR / "PROTOCOL.md"

CONFIG_DIR = Path(os.environ.get("AGENT_MEMORY_CONFIG_DIR", "~/.config/agent-memory")).expanduser()
CONFIG_FILE = CONFIG_DIR / "config.json"


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
