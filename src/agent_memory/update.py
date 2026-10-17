"""Whether a newer release is out, and updating this copy when `uv tool` installed it.

The check asks PyPI for the package's latest version (only the package name goes out) and keeps the
answer for a day. Automatic checks can be turned off with `check_updates: false` in config.json.
"""

import datetime as _dt
import importlib.metadata
import json
import re
import shlex
import shutil
import subprocess
import sys
import time
import tomllib
import urllib.request
from pathlib import Path

from . import config

PACKAGE = "agent-memory-git"
INDEX = f"https://pypi.org/pypi/{PACKAGE}/json"
CHECK_EVERY = 24 * 3600
CACHE_NAME = "update-check.json"
# how to update, by how this copy was installed; for `uv tool` it depends on the install, see upgrade_args
COMMANDS = {
    "uvx": f'uvx --refresh --from "{PACKAGE}[ui]" mem ui',
    "dev": "git pull && mem install",  # run in the checkout
    "other": f'pip install -U "{PACKAGE}[ui]" && mem install',
}


def _cache():
    return config.CONFIG_DIR / CACHE_NAME


def _cached():
    try:
        return json.loads(_cache().read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def current():
    try:
        return importlib.metadata.version(PACKAGE)
    except importlib.metadata.PackageNotFoundError:
        return None


def _key(version):
    """A version as numbers to compare: 0.1.10 > 0.1.9; a pre-release sorts before its release."""
    out = []
    for part in version.split("."):
        m = re.match(r"(\d+)(.*)", part)
        if not m:
            break
        out += [int(m.group(1)), 0 if m.group(2) else 1]
    return out


def newer(latest, cur):
    return bool(latest and cur) and _key(latest) > _key(cur)


def fetch_latest(timeout=5):
    """The latest release on PyPI, or None when PyPI cannot be reached."""
    try:
        with urllib.request.urlopen(INDEX, timeout=timeout) as r:
            return json.load(r)["info"]["version"]
    except Exception:  # some machines only reach PyPI through the system's certificates; curl uses those
        pass
    curl = shutil.which("curl")
    if not curl:
        return None
    try:
        r = subprocess.run([curl, "-fsSL", "--max-time", str(timeout), INDEX], capture_output=True, text=True)
        return json.loads(r.stdout)["info"]["version"] if r.returncode == 0 else None
    except (OSError, ValueError, KeyError):
        return None


def _inside(path, root):
    try:
        return Path(path).resolve().is_relative_to(Path(root).resolve())
    except OSError:
        return False


def how_installed():
    """'uv-tool' when uv can update this copy in place; else 'dev', 'uvx' or 'other'."""
    try:
        direct = importlib.metadata.distribution(PACKAGE).read_text("direct_url.json")
    except importlib.metadata.PackageNotFoundError:
        return "dev"
    if direct and json.loads(direct).get("dir_info", {}).get("editable"):
        return "dev"
    uv = shutil.which("uv")
    if uv:
        for kind, args in (("uv-tool", ["tool", "dir"]), ("uvx", ["cache", "dir"])):
            r = subprocess.run([uv, *args], capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip() and _inside(sys.prefix, r.stdout.strip()):
                return kind
    return "other"


def _receipt():
    """What `uv tool install` was given for this copy, from the receipt uv keeps in its environment."""
    try:
        return tomllib.loads((Path(sys.prefix) / "uv-receipt.toml").read_text("utf-8")).get("tool", {})
    except (OSError, ValueError):
        return {}


def _requirement(req, specifier=True):
    extras = f"[{','.join(req['extras'])}]" if req.get("extras") else ""
    return req["name"] + extras + (req.get("specifier", "") if specifier else "")


def upgrade_args():
    """The uv arguments that update this `uv tool` install. `uv tool upgrade` keeps a version given at
    install time (`agent-memory-git==0.1.3`), so such an install is installed again without it,
    keeping its extras, its Python and the packages added with `--with`."""
    tool = _receipt()
    reqs = tool.get("requirements", [])
    ours = next((r for r in reqs if r.get("name") == PACKAGE), {})
    simple = set(tool) <= {"requirements", "python", "entrypoints"} and all(
        set(r) <= {"name", "extras", "specifier"} for r in reqs
    )  # nothing a plain `uv tool install` would lose, such as a custom index or a git source
    if not (ours.get("specifier") and simple):
        return ["tool", "upgrade", PACKAGE]
    args = ["tool", "install", "--upgrade", _requirement(ours, specifier=False)]
    if tool.get("python"):
        args += ["--python", tool["python"]]
    for r in reqs:
        if r is not ours:
            args += ["--with", _requirement(r)]
    return args


def _uv_command(args):
    return f"{shlex.join(['uv', *args])} && mem install"


def status(force=False):
    """What the page shows: this version, the latest one known, and how to update."""
    auto = config.load().get("check_updates", True)
    cached = _cached()
    if force or (auto and time.time() - cached.get("checked", 0) > CHECK_EVERY):
        latest = fetch_latest()
        if latest:
            cached = {"checked": time.time(), "latest": latest}
            _cache().parent.mkdir(parents=True, exist_ok=True)
            _cache().write_text(json.dumps(cached), "utf-8")
    cur, latest, method = current(), cached.get("latest"), how_installed()
    checked = cached.get("checked")
    return {
        "current": cur,
        "latest": latest,
        "available": newer(latest, cur),
        "checked": _dt.datetime.fromtimestamp(checked).astimezone().isoformat() if checked else None,
        "auto": auto,
        "method": method,
        "command": _uv_command(upgrade_args()) if method == "uv-tool" else COMMANDS[method],
        "oneClick": method == "uv-tool",
    }


def _tail(*outputs, lines=12):
    text = "\n".join(o.strip() for o in outputs if o and o.strip())
    return "\n".join(text.splitlines()[-lines:])


def upgrade():
    """The uv update (see upgrade_args), then `mem install` from the upgraded code. Returns what happened."""
    if how_installed() != "uv-tool":
        return {"ok": False, "error": "This copy was not installed with `uv tool`; update it with the command shown."}
    before = current()
    args = upgrade_args()
    up = subprocess.run([shutil.which("uv"), *args], capture_output=True, text=True, timeout=600)
    if up.returncode != 0:
        return {"ok": False, "error": f"`{shlex.join(['uv', *args])}` failed.", "log": _tail(up.stdout, up.stderr)}
    # a new process, so both run the upgraded code
    after = subprocess.run(
        [sys.executable, "-c", f"import importlib.metadata as m; print(m.version({PACKAGE!r}))"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if after in ("", before):  # nothing new installed, so nothing for mem install to refresh
        known = _cached().get("latest")
        missed = newer(known, before)  # e.g. a version bound uv kept; its output says why
        return {
            "ok": not missed,
            "from": before,
            "to": before,
            "changed": False,
            "error": f"uv did not install {known}; its output is below." if missed else None,
            "log": _tail(up.stdout, up.stderr),
        }
    inst = subprocess.run(
        [sys.executable, "-m", "agent_memory", "install"], capture_output=True, text=True, timeout=120
    )
    return {
        "ok": inst.returncode == 0,
        "from": before,
        "to": after,
        "changed": True,
        "error": None if inst.returncode == 0 else "mem install failed after the upgrade.",
        "log": _tail(up.stdout, up.stderr, inst.stdout, inst.stderr),
    }
