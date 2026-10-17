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
DATA = "~/agent-memory-data"  # where the demo's data repository appears to be
# what the demo offers to search for, to show search by meaning across languages
QUERIES = ["payments are failing", "partition the data", "部署", "数据库迁移"]


def snapshot():
    """Everything the demo page asks the server for, answered once from the demo memories."""
    sys.path.insert(0, str(ROOT / "src"))
    from agent_memory import config, demo, ui, ui_server

    if not ui.model_ready():
        sys.exit("The snapshot needs the embedding model for similar memories and search: run `mem ui --fetch-model`.")
    with tempfile.TemporaryDirectory() as tmp:
        data = demo.make(Path(tmp) / "data")
        app = ui_server.UiApp(data, semantic=True)
        try:
            state = app.current()
            out = {
                "fingerprint": demo.fingerprint(),
                "state": {**state, "sync": {"remote": True, "ahead": 0}},
                "activity": app.activity(),
                "previews": {p: app.index_preview(p) for p in ["", *(p["key"] for p in state["places"])]},
                "settings": {
                    **app.settings(),
                    "remote": "git.example.com/agent-memory-data",
                    "sync": {"remote": True, "ahead": 0},
                    "keywordStopwords": [],
                },
                "doctor": {"checks": [{"ok": True, "text": text} for text in DOCTOR]},
                "queries": QUERIES,
                "search": {q: app.search(q) for q in QUERIES},
            }
        finally:
            if app.encoder:
                app.encoder.close()
        text = json.dumps(out, ensure_ascii=False, indent=1)
        # paths on this machine become the ones a reader would have
        paths = [(str(p), DATA) for p in (data.resolve(), data)] + [
            (str(p), "~") for p in (Path(tmp).resolve(), Path(tmp))
        ]
        for real, shown in [*paths, (str(config.BIN), "~/.local/bin/mem")]:
            text = text.replace(real, shown)
    text = re.sub(r'"generated": "[^"]+"', '"generated": ""', text)
    home = str(Path.home())
    assert home not in text, "a path from this machine is still in the snapshot"
    SNAPSHOT.write_text(text + "\n", "utf-8")
    print(f"wrote {SNAPSHOT.relative_to(ROOT)} ({len(text) // 1024} KB)")


DOCTOR = [
    f"data repository: {DATA}",
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
    snap["settings"]["version"] = version
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
