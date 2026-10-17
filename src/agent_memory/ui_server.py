"""The local server behind `mem ui`: the memory list, search, and edits.

Listens on 127.0.0.1 only. The page gets a per-run token in its URL fragment
and sends it on every API call; Host and Origin are checked too, so other
pages in the browser cannot read or change memories.

Every edit, addition or deletion is written to the data repository and
committed on its own (only the file it touched), then pushed in the
background like hook commits; Undo reverts that commit.
"""

import hashlib
import importlib.metadata
import json
import os
import re
import secrets
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np

from . import config, frontmatter, gitsync, profiles, select, store, ui, update
from .context import detect, hostname, normalize_remote
from .util import SCOPES, TYPES, atomic_write, id_path, log_exc, new_id, now_iso, slugify

STATIC = Path(__file__).with_name("webui")  # the page: plain HTML, CSS and JavaScript modules, no build step
MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".woff2": "font/woff2",
}
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)
RESTART_TOKEN = "AGENT_MEMORY_UI_TOKEN"
PLACE_FIELDS = ("cwd", "git_root", "git_remote", "git_branch")
SEARCH_HITS = 8
ACTIVITY_COMMITS = 2000
HOOK_LIMIT = 10000  # what Claude Code injects at most from a hook
COUNTS = re.compile(r"memory: \+(\d+) ~(\d+) -(\d+)")
UI_SUBJECT = re.compile(r"memory: (add|edit|delete|undo) (?:(\d+) memories)?")


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


class UiApp:
    def __init__(self, data_dir, semantic=True, encoder=None):
        self.data = Path(data_dir)
        self.mdir = store.memories_dir(data_dir)
        self.semantic = semantic
        self.lock = threading.Lock()
        self.encoder = encoder or (ui.QueryEncoder() if semantic else None)  # one model, whichever profile is open
        self.state, self.vectors, self.stamp_value = None, None, None
        self.refresh()
        if self.encoder and self.state.get("semantic"):  # load the model now, not on the first search
            threading.Thread(target=self.encoder.encode, args=("warm up",), daemon=True).start()

    # ------------------------------------------------------------ reads

    def stamp(self):
        head = gitsync.git(self.data, "rev-parse", "--short", "HEAD", timeout=5).stdout.strip()
        # a push in the background moves the upstream ref but not HEAD; without it a stale "not pushed" would stay
        pushed = gitsync.git(self.data, "rev-parse", "--short", "@{u}", timeout=5).stdout.strip()
        newest, count = 0, 0
        for path in self.mdir.rglob("*.md"):
            count += 1
            newest = max(newest, path.stat().st_mtime_ns)
        return f"{head}:{pushed}:{count}:{newest}"

    def refresh(self):
        with self.lock:
            out = []
            state = ui.build(self.data, semantic=self.semantic, vectors_out=out)
            self.state, self.vectors = state, (out[0] if out else None)
            self.stamp_value = self.stamp()
            self.state["stamp"] = self.stamp_value
            self.state["sync"] = self.sync_status()

    def current(self):
        if self.stamp() != self.stamp_value:  # an agent or another editor changed the store
            self.refresh()
        return self.state

    def sync_status(self):
        if not gitsync.has_remote(self.data):
            return {"remote": False}
        r = gitsync.git(self.data, "rev-list", "--count", "@{u}..HEAD", timeout=5)
        ahead = int(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip().isdigit() else 0
        return {"remote": True, "ahead": ahead}

    # ------------------------------------------------------------ insights and settings

    def activity(self):
        """Commits to the data repository, newest first: when, which tool, how many memories added, changed, deleted."""
        fmt = "%H%x1f%aI%x1f%s%x1f%(trailers:key=Tool,valueonly,separator=%x2C)%x1e"
        r = gitsync.git(self.data, "log", f"--format={fmt}", "-n", str(ACTIVITY_COMMITS), timeout=10)
        commits = []
        for record in r.stdout.split("\x1e") if r.returncode == 0 else []:
            parts = record.strip("\n").split("\x1f")
            if len(parts) != 4 or not parts[2].startswith("memory: "):
                continue
            sha, when, subject, tool = parts
            counts = COUNTS.match(subject)
            if counts:
                added, changed, deleted = map(int, counts.groups())
            else:
                ui_change = UI_SUBJECT.match(subject)
                verb, many = ui_change.groups() if ui_change else ("", None)
                n = int(many) if many else 1
                added, changed, deleted = (
                    (n if verb == "add" else 0),
                    (n if verb in ("edit", "undo") else 0),
                    (n if verb == "delete" else 0),
                )
            commits.append(
                {
                    "sha": sha[:10],
                    "date": when,
                    "subject": subject,
                    "tool": tool.strip() or None,
                    "added": added,
                    "changed": changed,
                    "deleted": deleted,
                }
            )
        return {"commits": commits}

    def index_preview(self, place):
        """The index a session gets at one of the known places, or with no place only the global part."""
        ctx = {}
        if place:
            known = {p["key"]: p.get("ctx", {}) for p in self.current().get("places", [])}
            if place not in known:
                raise ApiError(404, "unknown place")
            ctx = dict(known[place])
        memories = store.load_all(self.data)
        paths = {
            "memories": str(self.mdir),
            "staging": str(self.data / "staging" / "<session>"),
            "mem": str(config.BIN),
        }
        text = select.render(memories, ctx, paths, profile=profiles.active_name())
        globals_, here = select.visible(memories, ctx)
        return {"text": text, "chars": len(text), "limit": HOOK_LIMIT, "global": len(globals_), "here": len(here)}

    def settings(self):
        remote = gitsync.git(self.data, "remote", "get-url", "origin", timeout=5)
        url = remote.stdout.strip() if remote.returncode == 0 else ""
        try:
            version = importlib.metadata.version("agent-memory-git")
        except importlib.metadata.PackageNotFoundError:
            version = "dev"
        last = gitsync.git(self.data, "log", "-1", "--format=%aI", timeout=5).stdout.strip()
        return {
            "version": version,
            "dataDir": ui._short(str(self.data)),
            "name": self.data.name,
            "lastCommit": last or None,
            "remote": normalize_remote(url) if url else None,
            "remoteUrl": re.sub(r"(://)[^/@]+@", r"\1", url) or None,  # without any credentials in it
            "sync": self.sync_status(),
            "keywordStopwords": config.load().get("keyword_stopwords", []),
            "switchNote": config.load().get("switch_note", True),
            "model": {
                "name": ui.MODEL["name"],
                "ready": ui.model_ready(),
                "dir": ui._short(str(ui.model_dir())),
                "fetch": "mem ui --fetch-model",
                "size": "about 625 MB",
            },
            # with no memories yet there is nothing to embed, but searching by meaning works once there are
            "semantic": bool(self.state.get("semantic")) or (self.semantic and not self.state.get("memories")),
        }

    def set_settings(self, p):
        """Change keyword_stopwords, check_updates, switch_note, or several."""
        cfg = config.load()
        if "keyword_stopwords" in p:
            words = p["keyword_stopwords"]
            if not isinstance(words, list) or not all(isinstance(w, str) for w in words):
                raise ApiError(400, "keyword_stopwords must be a list of words")
            cfg["keyword_stopwords"] = sorted({w.strip().lower() for w in words if w.strip()})
        if "check_updates" in p:
            if not isinstance(p["check_updates"], bool):
                raise ApiError(400, "check_updates must be true or false")
            cfg["check_updates"] = p["check_updates"]
        if "switch_note" in p:
            if not isinstance(p["switch_note"], bool):
                raise ApiError(400, "switch_note must be true or false")
            cfg["switch_note"] = p["switch_note"]
        config.save(cfg)
        if "keyword_stopwords" in p:
            self.refresh()  # keywords are chosen when the state is built
        return self.settings()

    def check_update(self, p):
        return update.status(force=True)

    def run_update(self, p):
        return update.upgrade()

    def doctor(self):
        from .install import doctor_checks

        return {"checks": [{"ok": passed, "text": text} for passed, text in doctor_checks()]}

    def set_remote(self, p):
        """Connect the data repository to a remote ({url}), or disconnect it ({url: null})."""
        if p.get("url") is None:
            gitsync.disconnect(self.data)
            self.refresh()
            return {"ok": True, "message": "Disconnected; memories stay on this machine.", "settings": self.settings()}
        try:
            ok, message = gitsync.connect(self.data, p["url"])
        except ValueError as e:
            raise ApiError(400, str(e)) from None
        self.refresh()
        return {"ok": ok, "message": message, "settings": self.settings()}

    def sync(self, p):
        ok = gitsync.sync(self.data)
        self.refresh()
        return {"ok": ok, "sync": self.state["sync"]}

    def search(self, query):
        """Memories closest in meaning to the query (the page does word matching itself)."""
        query = (query or "").strip()
        if not query or not self.semantic or self.vectors is None or not self.state["semantic"]:
            return {"hits": [], "semantic": False}
        vec = self.encoder.encode(query)
        if vec is None:
            return {"hits": [], "semantic": False}
        scores = self.vectors @ vec
        order = np.argsort(-scores)[:SEARCH_HITS]
        ids = [self.state["memories"][int(i)]["id"] for i in order]
        return {"hits": [{"id": mid, "s": round(float(scores[i]), 3)} for mid, i in zip(ids, order)], "semantic": True}

    # ------------------------------------------------------------ writes

    def _find(self, mid):
        m = store.find(self.data, str(mid or ""))
        if not m or m["id"] != mid:
            raise ApiError(404, "That memory no longer exists; it may have been deleted elsewhere.")
        return m

    def _load(self, mid, base):
        path = self.mdir / self._find(mid)["rel"]
        text = path.read_text("utf-8")
        if base and hashlib.sha1(text.encode()).hexdigest()[:16] != base:
            raise ApiError(
                409,
                "This memory changed on disk after you opened it (an agent may have "
                "edited it). Close it and open it again to see the new version.",
            )
        meta, body = frontmatter.split(text)
        return path, meta, body

    def _place_ctx(self, place):
        if isinstance(place, dict) and place.get("path"):
            path = Path(str(place["path"])).expanduser()
            if not path.is_dir():
                raise ApiError(400, f"{place['path']} is not a folder on this machine.")
            return detect(str(path))
        key = place.get("key") if isinstance(place, dict) else place
        for p in self.state.get("places", []):
            if p["key"] == key:
                return dict(p["ctx"])
        raise ApiError(400, "Pick a place from the list or type a folder path.")

    def _commit(self, paths, message):
        rels = [str(Path(p).relative_to(self.data)) for p in ([paths] if isinstance(paths, (str, Path)) else paths)]
        gitsync.git(self.data, "add", "-A", "--", *rels)
        r = gitsync.git(
            self.data,
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-q",
            "--no-verify",
            "-m",
            message + "\n\nTool: ui",
            "--",
            *rels,
        )
        if r.returncode != 0:
            if "nothing" in r.stdout + r.stderr:
                return None
            raise ApiError(500, f"git commit failed: {(r.stderr or r.stdout).strip()}")
        head = gitsync.git(self.data, "rev-parse", "--short", "HEAD").stdout.strip()
        if gitsync.has_remote(self.data):
            gitsync.spawn_sync(self.data, push=True)
        return head

    def _write(self, fn):
        lock = gitsync.Lock(self.data, timeout=10)
        if not lock.__enter__():
            raise ApiError(503, "The memory repository is busy (a hook is committing). Try again.")
        try:
            result = fn()
        finally:
            lock.__exit__()
        self.refresh()
        return result

    def _apply(self, meta, body, change):
        changed = []
        for key, allowed in (("type", TYPES), ("scope", SCOPES)):
            if key in change and change[key] != meta.get(key):
                if change[key] not in allowed:
                    raise ApiError(400, f"Unknown {key} {change[key]!r}.")
                meta[key] = change[key]
                changed.append(key)
        if "description" in change:
            desc = " ".join(str(change["description"]).split())
            if not desc:
                raise ApiError(400, "A memory needs a one-line description.")
            if desc != meta.get("description"):
                meta["description"] = desc
                changed.append("description")
        if "body" in change and str(change["body"]).rstrip() != body.rstrip():
            body = str(change["body"])
            changed.append("body")
        source = dict(meta.get("source") or {})
        if change.get("place") and meta.get("scope") == "here":
            ctx = self._place_ctx(change["place"])
            old = source.get("cwd")
            for key in PLACE_FIELDS:
                source.pop(key, None)
            source.update({k: ctx[k] for k in PLACE_FIELDS if ctx.get(k)})
            if old and old != source.get("cwd"):
                source.setdefault("original_cwd", old)
            changed.append("place")
        if meta.get("scope") == "here" and not (source.get("cwd") or source.get("git_remote")):
            raise ApiError(400, "Pick the place where this memory should load.")
        if changed:
            meta["updated"] = now_iso()
        meta.pop("source", None)
        if source:
            meta["source"] = source  # provenance stays last, as the hooks write it
        return body, changed

    def create(self, p):
        typ, scope = p.get("type"), p.get("scope")
        if typ not in TYPES or scope not in SCOPES:
            raise ApiError(400, "Pick a type and where the memory loads.")
        desc = " ".join(str(p.get("description", "")).split())
        if not desc:
            raise ApiError(400, "A memory needs a one-line description.")
        source = {"tool": "ui", "host": hostname()}
        if scope == "here":
            if not p.get("place"):
                raise ApiError(400, "Pick the place where this memory should load.")
            ctx = self._place_ctx(p["place"])
            source.update({k: ctx[k] for k in PLACE_FIELDS if ctx.get(k)})
        name = slugify(p.get("name") or desc)
        mid = new_id(name)
        meta = {
            "id": mid,
            "name": name,
            "type": typ,
            "scope": scope,
            "description": desc,
            "created": now_iso(),
            "source": source,
        }
        path = self.mdir / id_path(mid)

        def write():
            atomic_write(path, frontmatter.join(meta, str(p.get("body", ""))))
            return {"id": mid, "commit": self._commit(path, f"memory: add {mid} (ui)")}

        return self._write(write)

    def edit(self, p):
        def write():
            path, meta, body = self._load(p.get("id"), p.get("base"))
            new_body, changed = self._apply(meta, body, p.get("change") or {})
            if not changed:
                return {"id": p.get("id"), "commit": None}
            atomic_write(path, frontmatter.join(meta, new_body))
            return {
                "id": p.get("id"),
                "commit": self._commit(path, f"memory: edit {p.get('id')} ({', '.join(changed)}) (ui)"),
            }

        return self._write(write)

    def delete(self, p):
        """Delete one memory ({id, base}) or several ({items: [{id, base}, ...]}) in one commit."""
        items = p.get("items") if isinstance(p.get("items"), list) else [p]
        if not items or len(items) > 200:
            raise ApiError(400, "Nothing to delete.")

        def write():
            loaded = [self._load(it.get("id"), it.get("base")) for it in items]  # all or nothing
            for path, _, _ in loaded:
                path.unlink()
            if len(loaded) == 1:
                message = f"memory: delete {items[0].get('id')} (ui)\n\n{loaded[0][1].get('description', '')}"
            else:
                message = f"memory: delete {len(loaded)} memories (ui)\n\n" + "\n".join(
                    f"- {it.get('id')}: {meta.get('description', '')}" for it, (_, meta, _) in zip(items, loaded)
                )
            return {"commit": self._commit([path for path, _, _ in loaded], message)}

        return self._write(write)

    def undo(self, p):
        rev = str(p.get("commit") or "")
        if not rev or len(rev) > 40 or any(c not in "0123456789abcdef" for c in rev):
            raise ApiError(400, "Bad commit id.")
        shown = gitsync.git(self.data, "show", "-s", "--format=%B", rev, timeout=10)
        if shown.returncode != 0 or "Tool: ui" not in shown.stdout:
            raise ApiError(400, "Only changes made on this page can be undone here.")

        def write():
            r = gitsync.git(self.data, "revert", "--no-commit", rev, timeout=20)
            if r.returncode != 0:
                gitsync.git(self.data, "revert", "--abort")
                raise ApiError(409, "Could not undo: that memory changed again since. Edit it instead.")
            gitsync.git(
                self.data,
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-q",
                "--no-verify",
                "-m",
                f"memory: undo {rev} (ui)\n\nTool: ui",
                timeout=10,
            )
            if gitsync.has_remote(self.data):
                gitsync.spawn_sync(self.data, push=True)
            return {"ok": True}

        return self._write(write)


# ---------------------------------------------------------------- profiles
# These change which repository the server shows, so they work on the server rather than on one UiApp.


def _profile_change(server, fn):
    if profiles.locked():
        raise ApiError(409, "AGENT_MEMORY_DATA picks the data repository for this run, so profiles cannot change.")
    before = profiles.listing()[1]
    try:
        out = fn() or {}
    except (profiles.ProfileError, ValueError) as e:
        raise ApiError(400, str(e)) from None
    if profiles.listing()[1] != before:  # the page now shows the profile new sessions use
        old = server.app
        server.app = UiApp(config.data_dir(), semantic=old.semantic, encoder=old.encoder)
    return {**profiles.summary(), **out}


def _access():
    from .install import refresh_access

    tools = refresh_access()
    return {"access": tools}


def profile_use(server, p):
    def use():
        profiles.use(str(p.get("id") or ""))

    return _profile_change(server, use)


def profile_add(server, p):
    def add():
        pid, note = profiles.add(
            str(p.get("folder") or "").strip(),
            remote=p.get("remote"),
            switch=p.get("switch", True) is not False,
            name=p.get("name"),
        )
        return {"id": pid, "message": note, **_access()}

    return _profile_change(server, add)


def profile_remove(server, p):
    def remove():
        profiles.remove(str(p.get("id") or ""))
        return _access()

    return _profile_change(server, remove)


class Handler(BaseHTTPRequestHandler):
    server_version = "agent-memory"
    POSTS = {
        "/api/create": "create",
        "/api/edit": "edit",
        "/api/delete": "delete",
        "/api/undo": "undo",
        "/api/settings": "set_settings",
        "/api/sync": "sync",
        "/api/remote": "set_remote",
        "/api/update/check": "check_update",
        "/api/update": "run_update",
    }
    PROFILE_POSTS = {
        "/api/profiles/use": profile_use,
        "/api/profiles/add": profile_add,
        "/api/profiles/remove": profile_remove,
    }

    def log_message(self, *args):
        pass

    def _send(self, status, payload, ctype="application/json; charset=utf-8"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        for k, v in (
            ("Content-Type", ctype),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            ("Referrer-Policy", "no-referrer"),
        ):
            self.send_header(k, v)
        if ctype.startswith("text/html"):
            self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        self.wfile.write(body)

    def _guard(self, api):
        if self.headers.get("Host", "") not in self.server.hosts:
            self._send(421, {"error": "wrong host"})
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://{h}" for h in self.server.hosts}:
            self._send(403, {"error": "cross-origin request refused"})
            return False
        if api and not secrets.compare_digest(self.headers.get("X-Mem-Token", ""), self.server.token):
            self._send(401, {"error": "This link has expired. Run `mem ui` again and use the new link."})
            return False
        return True

    def _run(self, fn):
        try:
            self._send(200, fn())
        except (BrokenPipeError, ConnectionResetError):
            pass  # the page went away (reload, closed tab) before the reply was written
        except ApiError as e:
            self._send(e.status, {"error": e.message})
        except Exception as e:
            log_exc(self.server.app.data, f"ui {self.path}")
            self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def do_GET(self):
        url = urlparse(self.path)
        api = url.path.startswith("/api/")
        if not self._guard(api):
            return
        if not api:
            return self._page(url.path.lstrip("/"))
        app, q = self.server.app, {k: v[0] for k, v in parse_qs(url.query).items()}
        routes = {
            "/api/state": app.current,
            "/api/stamp": lambda: {"stamp": app.stamp()},
            "/api/search": lambda: app.search(q.get("q")),
            "/api/activity": app.activity,
            "/api/index-preview": lambda: app.index_preview(q.get("place", "")),
            "/api/settings": app.settings,
            "/api/doctor": app.doctor,
            "/api/update": update.status,
            "/api/profiles": profiles.summary,
        }
        if url.path not in routes:
            return self._send(404, {"error": "not found"})
        self._run(routes[url.path])

    def _page(self, rel):
        """The page's files, and index.html for any other path so the page can route."""
        root = STATIC.resolve()
        target = (root / rel).resolve() if rel else None
        if target and target.is_file() and root in target.parents and target.suffix in MIME:
            return self._send(200, target.read_bytes(), MIME[target.suffix])
        if Path(rel).suffix in MIME:  # a file the page asked for that is not there
            return self._send(404, {"error": "not found"})
        return self._send(200, (root / "index.html").read_bytes(), MIME[".html"])

    def do_POST(self):
        url = urlparse(self.path)
        if not self._guard(True):
            return
        if url.path == "/api/restart":  # after an update: answer, then serve_forever ends and run() starts the new code
            self.server.restart = True
            self._send(200, {"restarting": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        method, change = self.POSTS.get(url.path), self.PROFILE_POSTS.get(url.path)
        if not method and not change:
            return self._send(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}") if length else {}
        except ValueError:
            return self._send(400, {"error": "bad JSON"})
        if change:
            return self._run(lambda: change(self.server, payload))
        self._run(lambda: getattr(self.server.app, method)(payload))


class Server(ThreadingHTTPServer):
    # The page is some twenty modules the browser asks for at once; with socketserver's backlog of 5 the
    # kernel resets the overflow, a module fails to load, and the page stays blank.
    request_queue_size = 128


def make_server(data_dir, port=8790, semantic=True):
    app = UiApp(data_dir, semantic=semantic)
    try:
        server = Server(("127.0.0.1", port), Handler)
    except OSError:
        server = Server(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    server.hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    # a restart after an update keeps the token, so the open page carries on
    server.token = os.environ.pop(RESTART_TOKEN, None) or secrets.token_urlsafe(18)
    server.restart = False
    server.app = app
    server.url = f"http://127.0.0.1:{port}/#t={server.token}"
    return server


def run(data_dir, port=8790, open_browser=True, semantic=True):
    if semantic and not ui.model_ready():
        print(
            "No local embedding model; similar memories use keywords only. "
            "Run `mem ui --fetch-model` (about 625 MB) to also search by meaning.",
            flush=True,
        )
    server = make_server(data_dir, port, semantic)
    print(f"Memories: {server.url}", flush=True)
    print("Keep this terminal open while you use it; Ctrl+C stops it.", flush=True)
    if open_browser:
        try:
            subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", server.url], check=False)
        except OSError:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
        if server.app.encoder:
            server.app.encoder.close()
    if server.restart:
        args = ["ui", "--port", str(server.server_address[1]), "--no-open"] + ([] if semantic else ["--keywords-only"])
        print("Restarting with the updated version...", flush=True)
        os.environ[RESTART_TOKEN] = server.token
        os.execv(sys.executable, [sys.executable, "-m", "agent_memory", *args])
