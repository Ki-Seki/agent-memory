"""Profiles: separate memory repositories to switch between, each a folder with an optional remote of its own.

config.json lists them under "profiles" and names the active one under "profile"; "data_dir" always holds the
active profile's folder, so the hooks and older versions of mem read the right one. A config from before
profiles has one implicit profile, "default", for its data_dir, written out once a second one is added.

A profile's name is two words picked at random when it is made, such as Quiet Harbor, and never changes; the
page draws its picture from the name.

New sessions load and save memories in the active profile. A session that is running when the profile changes
keeps committing to the one it started in, since its staging folder is there.
"""

import hashlib
import os
import re
import secrets
import shutil
from pathlib import Path

from . import config, gitsync
from .context import normalize_remote
from .util import HOME

DEFAULT = "default"
# names are one of each: soft, plain words, so that any pair reads kindly
ADJECTIVES = (
    "Amber", "Brave", "Breezy", "Bright", "Calm", "Cheery", "Cozy", "Crisp", "Dapper", "Dewy", "Gentle", "Golden",
    "Happy", "Hazy", "Jolly", "Kind", "Lucky", "Mellow", "Merry", "Misty", "Nimble", "Peachy", "Plucky", "Quiet",
    "Rosy", "Silver", "Sleepy", "Snowy", "Soft", "Sunny", "Swift", "Tidy", "Velvet", "Warm", "Wise", "Witty",
)  # fmt: skip
NOUNS = (
    "Acorn", "Biscuit", "Brook", "Button", "Clover", "Cloud", "Comet", "Daisy", "Dumpling", "Ember", "Feather", "Fern",
    "Harbor", "Koala", "Lantern", "Maple", "Meadow", "Mochi", "Muffin", "Noodle", "Orchard", "Otter", "Panda", "Pebble",
    "Pine", "Pudding", "Puffin", "Robin", "Sparrow", "Sprout", "Teapot", "Tulip", "Walnut", "Willow", "Wombat", "Zephyr",
)  # fmt: skip
# what a memory repository may hold at its top level besides memories/, so a profile never adopts other files
REPO_FILES = {".git", ".gitignore", ".gitattributes", "README.md", "memories", "staging", ".cache", ".DS_Store"}


class ProfileError(ValueError):
    pass


def locked():
    """AGENT_MEMORY_DATA picks the folder (the demo, a test, a background sync), so profiles do not apply."""
    return bool(os.environ.get("AGENT_MEMORY_DATA"))


def _found(cfg):
    listed = cfg.get("profiles")
    if isinstance(listed, dict) and listed:
        return {k: dict(v) for k, v in listed.items() if isinstance(v, dict) and v.get("data_dir")}
    if cfg.get("data_dir"):  # from before profiles: its name comes from its folder, so it stays the same
        return {DEFAULT: {"name": name_for(cfg["data_dir"]), "data_dir": cfg["data_dir"]}}
    return {}


def name_for(seed):
    """The name `seed` always gets."""
    n = int.from_bytes(hashlib.sha256(str(seed).encode()).digest()[:8], "big")
    return f"{ADJECTIVES[n % len(ADJECTIVES)]} {NOUNS[n // len(ADJECTIVES) % len(NOUNS)]}"


def new_name(found):
    """A name no profile in `found` has."""
    taken = {p["name"] for p in found.values()}
    while True:
        name = f"{secrets.choice(ADJECTIVES)} {secrets.choice(NOUNS)}"
        if name not in taken:
            return name


def generated(name):
    """Whether `name` is one this module could have made, which is all a profile may be called."""
    words = str(name).split(" ")
    return len(words) == 2 and words[0] in ADJECTIVES and words[1] in NOUNS


def listing(cfg=None):
    """(profiles as {id: {name, data_dir}}, the active id)."""
    cfg = config.load() if cfg is None else cfg
    found = _found(cfg)
    active = cfg.get("profile") if cfg.get("profile") in found else next(iter(found), None)
    return found, active


def dirs():
    """Every profile's folder, the active one first; only AGENT_MEMORY_DATA's while that is set."""
    if locked():
        return [config.data_dir()]
    found, active = listing()
    order = [active, *(k for k in found if k != active)] if active else []
    return [Path(found[k]["data_dir"]).expanduser() for k in order]


def active_name():
    """The active profile's name when there are several; with one, profiles go unmentioned."""
    if locked():
        return None
    found, active = listing()
    return found[active]["name"] if len(found) > 1 else None


def _save(cfg, found, active):
    cfg["profiles"] = found
    cfg["profile"] = active
    cfg["data_dir"] = found[active]["data_dir"]
    config.save(cfg)


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")


def find(key, found):
    """The id of the profile with this id or name; quiet-harbor and "quiet harbor" both find Quiet Harbor."""
    if key in found:
        return key
    for k, p in found.items():
        if _slug(p["name"]) == _slug(key):
            return k
    raise ProfileError(f"There is no profile {key!r}.")


def _same(a, b):
    return Path(a).expanduser().resolve() == Path(b).expanduser().resolve()


def _new_id(name, found):
    base, pid, n = _slug(name) or "profile", _slug(name) or "profile", 2
    while pid in found:
        pid, n = f"{base}-{n}", n + 1
    return pid


# ---------------------------------------------------------------- the folder


def _empty(folder):
    return not folder.exists() or (folder.is_dir() and not any(folder.iterdir()))


def _memory_repo(folder):
    """Whether folder looks like a memory repository: memories/, or nothing that is not one's own files."""
    return (folder / "memories").is_dir() or all(p.name in REPO_FILES for p in folder.iterdir())


def _push_new(folder):
    branch = gitsync.git(folder, "branch", "--show-current").stdout.strip() or "main"
    r = gitsync.git(folder, "push", "-q", "-u", "origin", branch, timeout=60)
    return "" if r.returncode == 0 else f" The push failed: {r.stderr.strip()}"


def prepare(folder, remote=None):
    """Make `folder` a memory repository for a new profile, and say what was done.

    An existing memory repository is used as it is, and gets the remote if it has none. A new or empty folder
    becomes one: cloned from the remote when there is one (an empty remote gets the new repository pushed to
    it), created otherwise. Anything else is refused, so a profile never commits files that are not memories.
    """
    from .install import init_repo

    folder = Path(folder).expanduser()
    if not folder.is_absolute():
        raise ProfileError("Give the folder as a full path, such as ~/agent-memory-work.")
    try:
        url = gitsync.remote_url(remote) if remote and str(remote).strip() else None
    except ValueError as e:
        raise ProfileError(str(e)) from None

    if (folder / ".git").exists():
        if not _memory_repo(folder):
            raise ProfileError(f"{folder} is a git repository with other files in it, not a memory repository.")
        if url and not gitsync.has_remote(folder):
            _, note = gitsync.connect(folder, url)
            return f"Using the memory repository there. {note}"
        kept = " It has a remote already, which stays." if url else ""
        return f"Using the memory repository there.{kept}"
    if not _empty(folder):
        raise ProfileError(f"{folder} has files in it and is not a memory repository. Pick a new or empty folder.")

    if not url:
        init_repo(folder)
        return "Created a new memory repository."
    made = not folder.exists()
    folder.parent.mkdir(parents=True, exist_ok=True)
    r = gitsync.git(folder.parent, "clone", "-q", url, str(folder), timeout=180)
    if r.returncode != 0 or not _memory_repo(folder):
        if made:
            shutil.rmtree(folder, ignore_errors=True)
        else:  # it was empty: leave it so
            for child in folder.iterdir():
                shutil.rmtree(child) if child.is_dir() else child.unlink()
        if r.returncode != 0:
            why = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "no answer"
            raise ProfileError(f"Could not clone the remote: {why}")
        raise ProfileError("That remote has other files in it, not a memory repository.")
    if gitsync.git(folder, "rev-parse", "--verify", "-q", "HEAD").returncode != 0:
        gitsync.git(folder, "symbolic-ref", "HEAD", "refs/heads/main")  # an empty remote: start on main
        init_repo(folder)
        return "Created a new memory repository and pushed it to the empty remote." + _push_new(folder)
    if init_repo(folder):  # a memory repository without the README or .gitignore
        return "Cloned the remote." + _push_new(folder)
    return "Cloned the remote."


# ---------------------------------------------------------------- changes


def use(key):
    cfg = config.load()
    found, _ = listing(cfg)
    pid = find(key, found)
    folder = Path(found[pid]["data_dir"]).expanduser()
    if not (folder / ".git").exists():
        raise ProfileError(f"{short(folder)} is not a memory repository any more; was it moved or deleted?")
    _save(cfg, found, pid)
    return pid


def add(folder, remote=None, switch=True, name=None):
    """Create a profile for `folder` (made ready by prepare): (id, what was done).

    It gets a new name, or `name` when that is one new_name could have given and no profile has (the page
    shows the name before the profile is made).
    """
    found, active = listing()
    folder = Path(folder).expanduser()
    for p in found.values():
        if folder.is_absolute() and _same(p["data_dir"], folder):
            raise ProfileError(f"The {p['name']} profile uses that folder already.")
    sandbox = os.environ.get("AGENT_MEMORY_DEMO")  # `mem ui --demo` (demo.ENV): leave nothing behind
    if sandbox and folder.is_absolute() and not folder.resolve().is_relative_to(Path(sandbox).resolve()):
        raise ProfileError(
            f"In the demo, a new profile's folder has to be inside {short(sandbox)}, which goes when it stops."
        )
    note = prepare(folder, remote)
    cfg = config.load()  # a clone can take a while; start from the config as it is now
    found, active = listing(cfg)
    if not (name and generated(name) and name not in {p["name"] for p in found.values()}):
        name = new_name(found)
    pid = _new_id(name, found)
    found[pid] = {"name": name, "data_dir": str(folder)}
    _save(cfg, found, pid if switch or not active else active)
    return pid, note


def remove(key):
    """Forget a profile; its folder and remote stay as they are. Returns the active id afterwards."""
    cfg = config.load()
    found, active = listing(cfg)
    pid = find(key, found)
    if len(found) == 1:
        raise ProfileError("This is the only profile; add another before removing it.")
    del found[pid]
    _save(cfg, found, active if active != pid else next(iter(found)))
    return cfg["profile"]


def set_folder(data_dir):
    """`mem init`: data_dir becomes the active profile's folder, or the profile that has it becomes active."""
    cfg = config.load()
    if not isinstance(cfg.get("profiles"), dict):
        cfg["data_dir"] = str(data_dir)
        return config.save(cfg)
    found, active = listing(cfg)
    has = next((k for k, p in found.items() if _same(p["data_dir"], data_dir)), None)
    if has:
        return _save(cfg, found, has)
    found[active]["data_dir"] = str(data_dir)
    _save(cfg, found, active)


# ---------------------------------------------------------------- for display


def short(path):
    home = str(HOME)
    path = str(path)
    return "~" + path[len(home) :] if path == home or path.startswith(home + "/") else path


def describe(pid, p, active):
    """One profile as the page and `mem profile list` show it."""
    folder = Path(p["data_dir"]).expanduser()
    ready = (folder / ".git").exists()
    url = gitsync.git(folder, "remote", "get-url", "origin", timeout=5).stdout.strip() if ready else ""
    memories = folder / "memories"
    return {
        "id": pid,
        "name": p["name"],
        "dataDir": short(folder),
        "active": pid == active,
        "ready": ready,
        "memories": sum(1 for _ in memories.rglob("*.md")) if memories.is_dir() else 0,
        "remote": normalize_remote(url) if url else None,
    }


def summary():
    found, active = listing()
    return {
        "locked": locked(),
        "demo": bool(os.environ.get("AGENT_MEMORY_DEMO")),  # no agent uses the demo's profiles
        "active": active,
        "next": new_name(found),  # what the next profile will be called
        "profiles": [] if locked() else [describe(k, p, active) for k, p in found.items()],
    }
