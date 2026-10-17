"""The project site: one landing page, and a live demo of mem ui on made-up memories.

    uv run --extra ui scripts/site.py snapshot   # save what the demo shows (needs the embedding model)
    uv run scripts/site.py build [OUT]           # assemble the site into OUT (default site/_build)
    uv run scripts/site.py serve [PORT]          # build, then serve it at http://127.0.0.1:PORT/

The site has no build step of its own: build copies site/ and puts mem ui's page under demo/, with
demo.js answering the page's calls from the saved snapshot instead of a server.
"""

import functools
import http.server
import json
import os
import re
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
WEBUI = ROOT / "src" / "agent_memory" / "webui"
SNAPSHOT = SITE / "demo" / "snapshot.json"
BUILD = SITE / "_build"
HOME = "~"  # where the demo's data repositories appear to be, one per profile (demo.PROFILES)
# what the demo offers to search for, to show search by meaning across languages
QUERIES = ["payments are failing", "partition the data", "部署", "数据库迁移"]


def snapshot():
    """Everything the demo page asks the server for, answered once from the demo memories of each profile."""
    sys.path.insert(0, str(ROOT / "src"))
    os.environ.pop("AGENT_MEMORY_DATA", None)  # the profiles pick the folder, as in `mem ui --demo`
    from agent_memory import config, demo, profiles, ui, ui_server

    if not ui.model_ready():
        sys.exit("The snapshot needs the embedding model for similar memories and search: run `mem ui --fetch-model`.")
    keep = {k: v for k, v in config.load().items() if k == "embed_model_dir"}
    with tempfile.TemporaryDirectory() as tmp:
        dirs = {pid: Path(tmp) / p["folder"] for pid, p in demo.PROFILES.items()}
        listed = {pid: {"name": p["name"], "data_dir": str(dirs[pid])} for pid, p in demo.PROFILES.items()}
        # a config of its own in tmp, so the index each profile shows names it as yours would
        config.CONFIG_DIR, config.CONFIG_FILE = Path(tmp) / "config", Path(tmp) / "config" / "config.json"
        out = {
            "fingerprint": demo.fingerprint(),
            "active": next(iter(listed)),
            "words": [profiles.ADJECTIVES, profiles.NOUNS],  # so the demo names new profiles as mem does
            "profiles": {},
        }
        encoder = None
        try:
            for pid, p in demo.PROFILES.items():
                demo.make(dirs[pid], profile=pid)
                config.save({**keep, "data_dir": str(dirs[pid]), "profiles": listed, "profile": pid})
                app = ui_server.UiApp(dirs[pid], semantic=True, encoder=encoder)
                encoder = app.encoder
                state = app.current()
                out["profiles"][pid] = {
                    "name": p["name"],
                    "dataDir": f"{HOME}/{p['folder']}",
                    "state": {**state, "sync": {"remote": True, "ahead": 0}},
                    "activity": app.activity(),
                    "previews": {q: app.index_preview(q) for q in ["", *(x["key"] for x in state["places"])]},
                    "settings": {
                        **app.settings(),
                        "remote": f"git.example.com/{p['folder']}",
                        "sync": {"remote": True, "ahead": 0},
                        "keywordStopwords": [],
                    },
                    "search": {q: app.search(q) for q in QUERIES},
                }
        finally:
            if encoder:
                encoder.close()
        out["doctor"] = {"checks": [{"ok": True, "text": text} for text in DOCTOR]}
        out["queries"] = QUERIES
        text = json.dumps(out, ensure_ascii=False, indent=1)
        # paths on this machine become the ones a reader would have
        paths = [(str(p), f"{HOME}/{p.name}") for d in dirs.values() for p in (d.resolve(), d)] + [
            (str(p), HOME) for p in (Path(tmp).resolve(), Path(tmp))
        ]
        for real, shown in [*paths, (str(config.BIN), "~/.local/bin/mem")]:
            text = text.replace(real, shown)
    text = re.sub(r'"generated": "[^"]+"', '"generated": ""', text)
    home = str(Path.home())
    assert home not in text, "a path from this machine is still in the snapshot"
    SNAPSHOT.write_text(text + "\n", "utf-8")
    print(f"wrote {SNAPSHOT.relative_to(ROOT)} ({len(text) // 1024} KB)")


DOCTOR = [
    "data repository: ~/agent-memory-data",  # demo.js names the folder of the profile it shows
    "install state: ~/.config/agent-memory/install-state.json",
    "Claude auto memory disabled",
    "Claude SessionStart hook",
    "Claude Stop hook",
    "Claude SessionEnd hook",
    "Claude CLAUDE.md imports PROTOCOL.md",
    "Claude's PROTOCOL.md copy is current (else run `mem install`)",
    "Codex SessionStart hook",
    "Codex Stop hook",
    "Codex SessionEnd hook",
    "Codex native memories disabled",
    "Codex AGENTS.md has the current protocol (else run `mem install`)",
    "`mem` on a new terminal's PATH (~/.local/bin)",
    "data repository has a remote",
    "no stuck staged files (0)",
    "no hook errors in the last 7 days (0)",
]


def build(out=BUILD):
    out = Path(out)
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(SITE, out, ignore=shutil.ignore_patterns("_build", ".DS_Store"))
    shutil.copytree(WEBUI, out / "demo", dirs_exist_ok=True)
    page = (WEBUI / "index.html").read_text("utf-8")
    page = page.replace('src="js/main.js"', 'src="demo.js"').replace(
        "<title>Memories · agent-memory</title>", "<title>Live demo · agent-memory</title>"
    )
    (out / "demo" / "index.html").write_text(page, "utf-8")
    version = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]["version"]
    snap = json.loads(SNAPSHOT.read_text("utf-8"))
    for profile in snap["profiles"].values():
        profile["settings"]["version"] = version
    (out / "demo" / "snapshot.json").write_text(json.dumps(snap, ensure_ascii=False), "utf-8")
    (out / ".nojekyll").write_text("")
    print(f"built the site into {out}")
    return out


def serve(port=8800):
    out = build()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"serving http://127.0.0.1:{port}/ (Ctrl+C stops)", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:] or ["build"]
    if cmd == "snapshot":
        snapshot()
    elif cmd == "build":
        build(*rest)
    elif cmd == "serve":
        serve(int(rest[0]) if rest else 8800)
    else:
        sys.exit(__doc__)
