import atexit
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(tempfile.mkdtemp(prefix="agent-memory-test-"))
atexit.register(shutil.rmtree, ROOT, ignore_errors=True)
os.environ["AGENT_MEMORY_CONFIG_DIR"] = str(ROOT / "config")
os.environ["CLAUDE_CONFIG_DIR"] = str(ROOT / "claude")
os.environ["CODEX_HOME"] = str(ROOT / "codex")
DATA = ROOT / "data"
os.environ["AGENT_MEMORY_DATA"] = str(DATA)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_memory import capture, frontmatter, hooks, install, select, store  # noqa: E402
from agent_memory.context import normalize_remote  # noqa: E402
from agent_memory.util import HOME  # noqa: E402


def run_hook(event, tool, payload):
    out = io.StringIO()
    with mock.patch("sys.stdin", io.StringIO(json.dumps(payload))), mock.patch("sys.stdout", out):
        hooks.main(event, tool)
    return out.getvalue()


def make_repo(path, remote=None):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    if remote:
        subprocess.run(["git", "-C", str(path), "remote", "add", "origin", remote], check=True)
    return os.path.realpath(path)


class FrontmatterTest(unittest.TestCase):
    def test_round_trip(self):
        meta = {"id": "20261014-x-abcd", "name": "x", "type": "feedback", "scope": "global",
                "description": "中文描述: with a colon #and hash", "supersedes": ["a", "b"],
                "source": {"tool": "codex", "cwd": "/Users/a b/c", "session_name": "🌟261014"}}
        text = frontmatter.join(meta, "Body line\n\n**Why:** because")
        back, body = frontmatter.split(text)
        self.assertEqual(back, meta)
        self.assertTrue(body.startswith("Body line"))

    def test_lenient_model_output(self):
        text = ("---\nname: foo\ntype: User\nscope: GLOBAL\nmetadata:\n  type: feedback\n"
                "supersedes:\n  - old-1\n  - old-2\n---\nThe fact.\n")
        meta, body = frontmatter.split(text)
        m = store.normalize(meta, body, "fallback")
        self.assertEqual((m["type"], m["scope"]), ("user", "global"))
        self.assertEqual(m["supersedes"], ["old-1", "old-2"])
        self.assertEqual(m["description"], "The fact.")

    def test_no_frontmatter(self):
        meta, body = frontmatter.split("just text")
        self.assertEqual(meta, {})
        self.assertEqual(body, "just text")


class RemoteTest(unittest.TestCase):
    def test_forms(self):
        for url in ["git@github.com:Ki-Seki/gallery.git", "https://github.com/Ki-Seki/gallery",
                    "https://user:tok@github.com/Ki-Seki/gallery.git",
                    "ssh://git@github.com:22/Ki-Seki/gallery.git"]:
            self.assertEqual(normalize_remote(url), "github.com/ki-seki/gallery", url)


class ScoreTest(unittest.TestCase):
    def test_location(self):
        shared = str(HOME / "repos" / "shared")
        child = shared + "/proj"
        ctx = {"cwd": shared, "host": "h"}
        self.assertEqual(select.location_score({"cwd": shared}, ctx), 100)
        self.assertEqual(select.location_score({"cwd": child}, ctx), 60)
        self.assertEqual(select.location_score({"cwd": shared}, {"cwd": child, "host": "h"}), 70)
        self.assertEqual(select.location_score({"cwd": str(HOME / "repos" / "other")}, ctx), 0)
        # ~/repos is too broad to pull in everything below it
        self.assertEqual(select.location_score({"cwd": child}, {"cwd": str(HOME / "repos")}), 0)
        remote = {"cwd": "/elsewhere", "git_remote": "github.com/a/b"}
        self.assertEqual(select.location_score(remote, {"cwd": "/x/y/z/w", "git_remote": "github.com/a/b"}), 80)

    def test_budget(self):
        mems = [{"id": f"m{i}", "name": "", "type": "feedback", "scope": "global" if i % 2 else "here",
                 "description": "x" * 140, "created": "", "updated": "", "supersedes": [],
                 "source": {"cwd": "/a/b/c/d"}, "rel": f"2026/10/m{i}.md"} for i in range(400)]
        text = select.render(mems, {"cwd": "/a/b/c/d", "host": "h"},
                             {"memories": "/m", "staging": "/s", "mem": "/bin/mem"})
        self.assertLess(len(text), 10000)
        self.assertIn("more: `mem list --global`", text)
        self.assertIn("more: `mem list --here`", text)


class EndToEndTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install.init_data(DATA)
        cls.proj = make_repo(ROOT / "work" / "a" / "proj", "git@github.com:Ki-Seki/proj.git")
        cls.other = make_repo(ROOT / "work" / "a" / "other")

    def test_capture_and_scope(self):
        payload = {"session_id": "s1", "cwd": self.proj, "transcript_path": None}
        out = json.loads(run_hook("session-start", "codex", payload))
        ctx_text = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("# Shared memory index", ctx_text)
        sdir = capture.session_dir(DATA, "codex", "s1")
        self.assertIn(str(sdir), ctx_text)

        (sdir / "local-fact.md").write_text(
            "---\nname: local-fact\ntype: project\nscope: here\n"
            "description: proj uses a frozen manifest\n---\nFact.\n", "utf-8")
        (sdir / "pref.md").write_text(
            "---\nname: reply-language\ntype: feedback\nscope: global\n"
            "description: reply in Chinese\n---\nPref.\n", "utf-8")
        run_hook("stop", "codex", payload)

        mems = {m["name"]: m for m in store.load_all(DATA)}
        self.assertEqual(set(mems), {"local-fact", "reply-language"})
        src = mems["local-fact"]["source"]
        self.assertEqual(src["tool"], "codex")
        self.assertEqual(src["session_id"], "s1")
        self.assertEqual(src["git_remote"], "github.com/ki-seki/proj")
        self.assertEqual(src["cwd"], self.proj)
        log = subprocess.run(["git", "-C", str(DATA), "log", "-1", "--format=%B"],
                             capture_output=True, text=True).stdout
        self.assertIn("memory: +2", log)
        self.assertIn("Session-Id: s1", log)

        here = json.loads(run_hook("session-start", "claude-code",
                                   {"session_id": "s2", "cwd": self.proj}))
        there = json.loads(run_hook("session-start", "claude-code",
                                    {"session_id": "s3", "cwd": self.other}))
        here = here["hookSpecificOutput"]["additionalContext"]
        there = there["hookSpecificOutput"]["additionalContext"]
        self.assertIn("frozen manifest", here)
        self.assertNotIn("frozen manifest", there)
        self.assertIn("reply in Chinese", here)
        self.assertIn("reply in Chinese", there)

        # in-place edit gets an `updated` stamp and its own commit
        path = store.memories_dir(DATA) / mems["local-fact"]["rel"]
        path.write_text(path.read_text("utf-8").replace("Fact.", "Fact, revised."), "utf-8")
        run_hook("stop", "claude-code", {"session_id": "s2", "cwd": self.proj})
        meta, body = store.read(path)
        self.assertIn("updated", meta)
        self.assertIn("revised", body)

        # supersedes deletes the replaced memory
        sdir2 = capture.session_dir(DATA, "claude-code", "s2")
        (sdir2 / "new.md").write_text(
            f"---\nname: local-fact-v2\ntype: project\nscope: here\n"
            f"supersedes: [{mems['local-fact']['id']}]\ndescription: v2\n---\nNew.\n", "utf-8")
        run_hook("session-end", "claude-code", {"session_id": "s2", "cwd": self.proj})
        names = {m["name"] for m in store.load_all(DATA)}
        self.assertIn("local-fact-v2", names)
        self.assertNotIn("local-fact", names)
        self.assertFalse(sdir2.exists())

    def test_hook_never_raises(self):
        with mock.patch("agent_memory.hooks.session_start", side_effect=RuntimeError("boom")):
            self.assertEqual(run_hook("session-start", "codex", {"session_id": "x"}), "")


class WorkdirTest(unittest.TestCase):
    def setUp(self):
        from agent_memory import workdir
        self.workdir = workdir
        self.home = ROOT / "home"
        for d in ("repos/shared/proj-a/src", "repos/shared/proj-b", "repos/other",
                  "Documents/Codex/2026-10-14/thread-x", "Library/Containers/app"):
            (self.home / d).mkdir(parents=True, exist_ok=True)
        (self.home / "repos/shared/proj-a/.git").mkdir(exist_ok=True)
        self.cwd = str(self.home / "Documents/Codex/2026-10-14/thread-x")

    def write(self, lines):
        path = ROOT / "transcript.jsonl"
        path.write_text("\n".join(json.dumps(l) for l in lines) + "\n")
        return str(path)

    def codex_call(self, text):
        return {"type": "response_item", "payload": {"type": "function_call", "arguments": text}}

    def test_throwaway_patterns(self):
        h = str(self.home)
        self.assertTrue(self.workdir.is_throwaway(self.cwd, self.home))
        self.assertTrue(self.workdir.is_throwaway("/x/scratch-workspaces/a/b", self.home))
        self.assertFalse(self.workdir.is_throwaway(h + "/Documents/Codex", self.home))
        self.assertFalse(self.workdir.is_throwaway(h + "/repos/shared", self.home))

    def test_descends_into_dominant_project(self):
        h = str(self.home)
        lines = [self.codex_call(f"cat {h}/repos/shared/proj-a/src/f{i}.py") for i in range(8)]
        lines += [self.codex_call(f"ls {h}/repos/shared/proj-b")]
        lines += [self.codex_call(f"ls {self.cwd}")] * 20  # the thread folder itself never wins
        lines += [self.codex_call(f"ls {h}/Library/Containers/app")] * 20  # not a project root
        got = self.workdir.infer(self.write(lines), self.cwd, home=self.home)
        self.assertEqual(got, h + "/repos/shared/proj-a")

    def test_stops_at_shared_folder_when_split(self):
        h = str(self.home)
        lines = [self.codex_call(f"ls {h}/repos/shared/proj-a")] * 3
        lines += [self.codex_call(f"ls {h}/repos/shared/proj-b")] * 3
        got = self.workdir.infer(self.write(lines), self.cwd, home=self.home)
        self.assertEqual(got, h + "/repos/shared")

    def test_dated_codex_folder_is_not_a_project(self):
        h = str(self.home)
        for t in ("a", "b"):
            (self.home / "Documents/Codex/2026-08-25" / t).mkdir(parents=True, exist_ok=True)
        # a session that looked at two Codex threads of one day worked in no project
        lines = [self.codex_call(f"cat {h}/Documents/Codex/2026-08-25/{t}/notes.md") for t in "ab" * 3]
        got = self.workdir.infer(self.write(lines), "/x/scratch-workspaces/s/t", home=self.home)
        self.assertIsNone(got)

    def test_dead_end_container_gives_way(self):
        h = str(self.home)
        for t in ("a", "b"):
            (self.home / "Documents/Codex/2026-08-25" / t).mkdir(parents=True, exist_ok=True)
        # mostly talking about Codex thread folders, but the work happened in proj-a
        lines = [self.codex_call(f"ls {h}/Documents/Codex/2026-08-25/{t}") for t in "ab" * 10]
        lines += [self.codex_call(f"cat {h}/repos/shared/proj-a/src/f{i}.py") for i in range(5)]
        got = self.workdir.infer(self.write(lines), "/x/scratch-workspaces/s/t", home=self.home)
        self.assertEqual(got, h + "/repos/shared/proj-a")

    def test_ignores_injected_instructions(self):
        h = str(self.home)
        injected = {"type": "response_item", "payload": {
            "type": "message", "role": "developer",
            "content": [{"text": f"memory: {h}/repos/other " * 50}]}}
        lines = [injected, self.codex_call(f"ls {h}/repos/shared/proj-a")]
        self.assertIsNone(self.workdir.infer(self.write(lines), self.cwd, home=self.home))

    def test_claude_transcript_and_excludes(self):
        h = str(self.home)
        lines = [{"type": "assistant", "message": {"content": f"edit {h}/repos/other/x.md"}}] * 5
        lines += [{"type": "attachment", "content": f"{h}/repos/shared/proj-a " * 50}]
        path = self.write(lines)
        self.assertEqual(self.workdir.infer(path, self.cwd, home=self.home), h + "/repos/other")
        self.assertIsNone(self.workdir.infer(path, self.cwd, exclude=[h + "/repos/other"],
                                             home=self.home))


def by_desc_kw(data, desc):
    return next(m for m in data["memories"] if m["description"] == desc)["keywords"]


class UiTest(unittest.TestCase):
    def setUp(self):
        from agent_memory import ui
        self.ui = ui

    def test_tokens_drop_noise_and_keep_words(self):
        words = self.ui.chinese_words(["汇报时给北京时间", "按北京时间说", "北京时间晚上"])
        self.assertIn("北京时间", words)
        self.assertNotIn("京时", words)  # a fragment of 北京时间, not a word
        toks = self.ui.tokens("Fix UTP in /Users/a/b/c.py at 3f2a9c1d, see S3 and the 北京时间 report", words)
        self.assertIn("utp", toks)
        self.assertIn("s3", toks)
        self.assertIn("北京时间", toks)
        self.assertNotIn("3f2a9c1d", toks)
        self.assertFalse(any("users" in t or t.endswith("py") for t in toks))

    def test_similar_memories_are_closer(self):
        docs = [("Highway access policy", "Glimpse route keeps warp access on Highway."),
                ("Highway route ACL", "Match Tuna route on Highway uses warp access only."),
                ("Reply language", "Write replies in Chinese for this user."),
                ("Commit rules", "Each commit does one thing; ask before push.")]
        x, vocab = self.ui.vectorize(docs)
        sim = x @ x.T
        self.assertGreater(sim[0, 1], sim[0, 2])
        self.assertGreater(sim[0, 1], sim[0, 3])

    def test_build_state(self):
        data_dir = ROOT / "ui-data"
        shutil.rmtree(data_dir, ignore_errors=True)
        for i, (desc, body) in enumerate([
                ("Highway access policy", "Glimpse route keeps warp access."),
                ("Highway route ACL", "Match Tuna route uses warp access only."),
                ("Reply language", "Write replies in Chinese."),
                ("Commit rules", "Each commit does one thing."),
                ("Push rules", "Ask before every push and commit.")]):
            mdir = data_dir / "memories" / "2026" / "10"
            mdir.mkdir(parents=True, exist_ok=True)
            meta = {"id": f"m{i}", "name": f"m{i}", "type": "feedback", "scope": "global",
                    "description": desc, "created": "2026-10-01T10:00:00+08:00", "source": {"tool": "cli"}}
            (mdir / f"m{i}.md").write_text(frontmatter.join(meta, body))
        with mock.patch.object(self.ui, "model_ready", return_value=False):  # no model in tests
            data = self.ui.build(data_dir)
        self.assertFalse(data["semantic"])
        self.assertEqual(len(data["memories"]), 5)
        m = data["memories"][0]
        self.assertTrue(m["raw"].startswith("---\nid: m"))  # the full file, for the File tab
        self.assertEqual(m["meta"]["source"], {"tool": "cli"})
        self.assertEqual(m["tool"], "cli")
        self.assertIn("warp", [k["k"] for k in by_desc_kw(data, "Highway access policy")])
        by_desc = {mm["description"]: mm for mm in data["memories"]}
        first = by_desc["Highway access policy"]["similar"][0]["i"]
        self.assertEqual(data["memories"][first]["description"], "Highway route ACL")

    def test_keywords_prefer_names(self):
        import numpy as np
        vocab = ["actually", "choose", "routes", "utp", "检索"]
        x = np.array([[0.9, 0.6, 0.5, 0.45, 0.4]])
        forms = {"choose": "Choose", "utp": "UTP"}
        picks = self.ui.keyword_picks(x, vocab, forms, k=3)[0]
        self.assertEqual([vocab[j] for j in picks], ["utp", "检索", "choose"])  # "actually" is generic

    def test_closeness_spreads_bunched_cosines(self):
        import numpy as np
        rng = np.random.default_rng(1)
        base = rng.normal(size=16)
        v = base + 0.6 * rng.normal(size=(12, 16))  # every pair similar, like raw embeddings
        v /= np.linalg.norm(v, axis=1, keepdims=True)
        c = self.ui.closeness(v)
        off = c[~np.eye(12, dtype=bool)]
        self.assertAlmostEqual(float(off.max()), 1.0)
        self.assertLess(float(np.median(off)), 0.01)  # a typical pair reads as about 0
        self.assertTrue((np.diag(c) == 1).all())

    def test_prose_drops_bookkeeping(self):
        body = ("# Task Group: Highway\n### rollout_summary_files\n- rollout_summaries/2026-x.md (cwd=/Users/a/b)\n"
                "Keep warp access on `glimpse` at /Users/a/repo/file.py, commit 3f2a9c1d.")
        text = self.ui.prose("Highway policy", body)
        self.assertIn("warp access", text)
        self.assertNotIn("rollout_summaries", text)
        self.assertNotIn("/Users", text)
        self.assertNotIn("3f2a9c1d", text)


class UiServerTest(unittest.TestCase):
    """Drive the `mem ui` API the way the page does, without the embedding model."""

    @classmethod
    def setUpClass(cls):
        import threading
        from agent_memory import ui, ui_server
        cls.data = ROOT / "ui-server-data"
        shutil.rmtree(cls.data, ignore_errors=True)
        mdir = cls.data / "memories" / "2026" / "10"
        mdir.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(cls.data)], check=True)
        for name, desc in (("alpha", "alpha pref"), ("beta", "beta pref"), ("gamma", "gamma fact")):
            meta = {"id": name, "name": name, "type": "feedback", "scope": "global", "description": desc,
                    "created": "2026-10-01T10:00:00+08:00", "source": {"tool": "cli"}}
            (mdir / f"{name}.md").write_text(frontmatter.join(meta, desc.upper()))
        subprocess.run(["git", "-C", str(cls.data), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(cls.data), "-c", "commit.gpgsign=false", "commit", "-qm", "seed"], check=True)
        cls.patch = mock.patch.object(ui, "model_ready", return_value=False)
        cls.patch.start()
        cls.server = ui_server.make_server(cls.data, port=0, semantic=False)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.patch.stop()

    def call(self, path, body=None, token=None, host=None, origin=None):
        import urllib.error
        import urllib.request
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}",
                                     data=None if body is None else json.dumps(body).encode(),
                                     method="GET" if body is None else "POST")
        req.add_header("X-Mem-Token", self.server.token if token is None else token)
        for k, v in (("Host", host), ("Origin", origin)):
            if v:
                req.add_header(k, v)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def mem(self, mid):
        status, state = self.call("/api/state")
        self.assertEqual(status, 200)
        return next((m for m in state["memories"] if m["id"] == mid), None)

    def test_guards(self):
        self.assertEqual(self.call("/api/state", token="nope")[0], 401)
        self.assertEqual(self.call("/api/state", host="evil.example")[0], 421)
        self.assertEqual(self.call("/api/edit", {"id": "alpha"}, origin="http://evil.example")[0], 403)
        self.assertEqual(self.call("/api/search?q=x")[1]["semantic"], False)

    def test_edit_conflict_undo(self):
        m = self.mem("alpha")
        status, res = self.call("/api/edit", {"id": "alpha", "base": m["hash"],
                                              "change": {"description": "alpha pref, edited", "body": "New text."}})
        self.assertEqual(status, 200, res)
        edited = self.mem("alpha")
        self.assertEqual(edited["description"], "alpha pref, edited")
        self.assertIn("updated", edited["meta"])
        self.assertEqual(list(edited["meta"])[-1], "source")  # provenance stays last
        self.assertEqual(self.call("/api/edit", {"id": "alpha", "base": m["hash"], "change": {"body": "x"}})[0], 409)
        self.assertEqual(self.call("/api/undo", {"commit": res["commit"]})[0], 200)
        self.assertEqual(self.mem("alpha")["description"], "alpha pref")

    def test_create_delete_undo(self):
        status, res = self.call("/api/create", {"type": "project", "scope": "here", "description": "new fact",
                                                "body": "N.", "place": {"path": str(ROOT)}})
        self.assertEqual(status, 200, res)
        new = self.mem(res["id"])
        self.assertEqual(new["meta"]["source"]["cwd"], os.path.realpath(ROOT))
        self.assertEqual(self.call("/api/create", {"type": "project", "scope": "here", "description": "x"})[0], 400)
        status, gone = self.call("/api/delete", {"id": res["id"], "base": new["hash"]})
        self.assertEqual(status, 200)
        self.assertIsNone(self.mem(res["id"]))
        self.call("/api/undo", {"commit": gone["commit"]})
        self.assertIsNotNone(self.mem(res["id"]))
        log = subprocess.run(["git", "-C", str(self.data), "log", "--format=%s", "-3"], capture_output=True,
                             text=True).stdout
        self.assertIn("memory: undo", log)


    def test_bulk_delete_is_one_commit(self):
        ids = []
        for desc in ("bulk one", "bulk two"):
            status, res = self.call("/api/create", {"type": "project", "scope": "global", "description": desc, "body": "B."})
            self.assertEqual(status, 200, res)
            ids.append(res["id"])
        items = [{"id": i, "base": self.mem(i)["hash"]} for i in ids]
        before = subprocess.run(["git", "-C", str(self.data), "rev-list", "--count", "HEAD"], capture_output=True, text=True).stdout
        status, res = self.call("/api/delete", {"items": items + [{"id": "missing-id"}]})
        self.assertEqual(status, 404)  # all or nothing
        self.assertIsNotNone(self.mem(ids[0]))
        status, res = self.call("/api/delete", {"items": items})
        self.assertEqual(status, 200, res)
        self.assertTrue(all(self.mem(i) is None for i in ids))
        after = subprocess.run(["git", "-C", str(self.data), "rev-list", "--count", "HEAD"], capture_output=True, text=True).stdout
        self.assertEqual(int(after) - int(before), 1)
        self.assertEqual(self.call("/api/undo", {"commit": res["commit"]})[0], 200)
        self.assertTrue(all(self.mem(i) is not None for i in ids))


class SyncTest(unittest.TestCase):
    def test_two_machines_converge(self):
        from agent_memory import gitsync
        bare = ROOT / "remote.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
        install.init_data(DATA)
        gitsync.git(DATA, "remote", "add", "origin", str(bare))
        gitsync.git(DATA, "push", "-q", "-u", "origin", "main")
        other = ROOT / "machine-b"
        subprocess.run(["git", "clone", "-q", str(bare), str(other)], check=True)

        for repo, name in ((DATA, "from-a"), (other, "from-b")):
            path = repo / "memories" / "2026" / "10" / f"{name}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"---\nid: {name}\ntype: user\nscope: global\n---\n{name}\n")
            gitsync.commit(repo, f"memory: {name}")

        self.assertTrue(gitsync.sync(DATA))
        self.assertTrue(gitsync.sync(other))
        self.assertTrue(gitsync.sync(DATA))
        for repo in (DATA, other):
            names = {p.stem for p in (repo / "memories").rglob("*.md")}
            self.assertTrue({"from-a", "from-b"} <= names, repo)
        gitsync.git(DATA, "remote", "remove", "origin")


CONFIG_TOML = '''model = "m"

[features]
memories = true

[memories]
generate_memories = true
use_memories = true

[hooks.state]

[hooks.state."/x/hooks.json:stop:0:0"]
enabled = false

[[skills.config]]
path = "/x/SKILL.md"
'''

HOOKS_JSON = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "otter Stop"}]}]}}

SETTINGS = {"permissions": {"allow": ["Bash(ls:*)"]},
            "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "other"}]}]}}


class InstallTest(unittest.TestCase):
    def setUp(self):
        install.init_data(DATA)
        for d in (install.CLAUDE_DIR, install.CODEX_DIR):
            d.mkdir(parents=True, exist_ok=True)
        (install.CLAUDE_DIR / "settings.json").write_text(json.dumps(SETTINGS, indent=2) + "\n")
        (install.CODEX_DIR / "config.toml").write_text(CONFIG_TOML)
        (install.CODEX_DIR / "hooks.json").write_text(json.dumps(HOOKS_JSON, indent=2) + "\n")
        (install.CODEX_DIR / "AGENTS.md").write_text("")
        install.STATE_FILE.unlink(missing_ok=True)

    def snapshot(self):
        files = [install.CLAUDE_DIR / "settings.json", install.CLAUDE_DIR / "CLAUDE.md",
                 install.CODEX_DIR / "config.toml", install.CODEX_DIR / "hooks.json",
                 install.CODEX_DIR / "AGENTS.md"]
        return {str(f): f.read_text() if f.exists() else None for f in files}

    def test_install_uninstall_round_trip(self):
        before = self.snapshot()
        rc = ROOT / "zshrc"
        rc.write_text("export FOO=1\n")
        rc_before = rc.read_text()
        with mock.patch.object(install, "LOCAL_BIN", ROOT / "bin" / "mem"), \
                mock.patch.object(install, "_login_path", return_value=["/usr/bin"]), \
                mock.patch.object(install, "_rc_file", return_value=rc), \
                mock.patch("sys.stdout", io.StringIO()):
            install.install()
            mid = self.snapshot()
            settings = json.loads(mid[str(install.CLAUDE_DIR / "settings.json")])
            self.assertIs(settings["autoMemoryEnabled"], False)
            self.assertEqual(len(settings["hooks"]["SessionStart"]), 2)
            import tomllib
            toml = tomllib.loads(mid[str(install.CODEX_DIR / "config.toml")])
            self.assertIs(toml["memories"]["use_memories"], False)
            self.assertIn(str(DATA), toml["sandbox_workspace_write"]["writable_roots"])
            self.assertEqual(toml["skills"]["config"][0]["path"], "/x/SKILL.md")
            self.assertIn("Shared memory", mid[str(install.CODEX_DIR / "AGENTS.md")])
            self.assertIn("@", mid[str(install.CLAUDE_DIR / "CLAUDE.md")])
            self.assertIn(install.PATH_LINE, rc.read_text())

            install.install()  # idempotent
            self.assertEqual(self.snapshot(), mid)

            # tools keep writing their own state while we are installed
            cfg = install.CODEX_DIR / "config.toml"
            cfg.write_text(cfg.read_text() + '\n[projects."/new"]\ntrust_level = "trusted"\n')

            install.uninstall()
        after = self.snapshot()
        self.assertEqual(rc.read_text(), rc_before)
        for path, text in before.items():
            if path.endswith("config.toml"):
                self.assertEqual(after[path], text + '\n[projects."/new"]\ntrust_level = "trusted"\n')
            else:
                self.assertEqual(after[path], text, path)


if __name__ == "__main__":
    unittest.main()
