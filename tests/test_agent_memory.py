import atexit
import io
import json
import os
import re
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

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
        meta = {
            "id": "20261014-x-abcd",
            "name": "x",
            "type": "feedback",
            "scope": "global",
            "description": "中文描述: with a colon #and hash",
            "supersedes": ["a", "b"],
            "source": {"tool": "codex", "cwd": "/Users/a b/c", "session_name": "🌟261014"},
        }
        text = frontmatter.join(meta, "Body line\n\n**Why:** because")
        back, body = frontmatter.split(text)
        self.assertEqual(back, meta)
        self.assertTrue(body.startswith("Body line"))

    def test_lenient_model_output(self):
        text = (
            "---\nname: foo\ntype: User\nscope: GLOBAL\nmetadata:\n  type: feedback\n"
            "supersedes:\n  - old-1\n  - old-2\n---\nThe fact.\n"
        )
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
        for url in [
            "git@github.com:Ki-Seki/gallery.git",
            "https://github.com/Ki-Seki/gallery",
            "https://user:tok@github.com/Ki-Seki/gallery.git",
            "ssh://git@github.com:22/Ki-Seki/gallery.git",
        ]:
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
        mems = [
            {
                "id": f"m{i}",
                "name": "",
                "type": "feedback",
                "scope": "global" if i % 2 else "here",
                "description": "x" * 140,
                "created": "",
                "updated": "",
                "supersedes": [],
                "source": {"cwd": "/a/b/c/d"},
                "rel": f"2026/10/m{i}.md",
            }
            for i in range(400)
        ]
        text = select.render(
            mems, {"cwd": "/a/b/c/d", "host": "h"}, {"memories": "/m", "staging": "/s", "mem": "/bin/mem"}
        )
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
            "---\nname: local-fact\ntype: project\nscope: here\ndescription: proj uses a frozen manifest\n---\nFact.\n",
            "utf-8",
        )
        (sdir / "pref.md").write_text(
            "---\nname: reply-language\ntype: feedback\nscope: global\ndescription: reply in Chinese\n---\nPref.\n",
            "utf-8",
        )
        run_hook("stop", "codex", payload)

        mems = {m["name"]: m for m in store.load_all(DATA)}
        self.assertEqual(set(mems), {"local-fact", "reply-language"})
        src = mems["local-fact"]["source"]
        self.assertEqual(src["tool"], "codex")
        self.assertEqual(src["session_id"], "s1")
        self.assertEqual(src["git_remote"], "github.com/ki-seki/proj")
        self.assertEqual(src["cwd"], self.proj)
        log = subprocess.run(
            ["git", "-C", str(DATA), "log", "-1", "--format=%B"], capture_output=True, text=True
        ).stdout
        self.assertIn("memory: +2", log)
        self.assertIn("Session-Id: s1", log)

        here = json.loads(run_hook("session-start", "claude-code", {"session_id": "s2", "cwd": self.proj}))
        there = json.loads(run_hook("session-start", "claude-code", {"session_id": "s3", "cwd": self.other}))
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
            f"supersedes: [{mems['local-fact']['id']}]\ndescription: v2\n---\nNew.\n",
            "utf-8",
        )
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
        for d in (
            "repos/shared/proj-a/src",
            "repos/shared/proj-b",
            "repos/other",
            "Documents/Codex/2026-10-14/thread-x",
            "Library/Containers/app",
        ):
            (self.home / d).mkdir(parents=True, exist_ok=True)
        (self.home / "repos/shared/proj-a/.git").mkdir(exist_ok=True)
        self.cwd = str(self.home / "Documents/Codex/2026-10-14/thread-x")

    def write(self, lines):
        path = ROOT / "transcript.jsonl"
        path.write_text("\n".join(json.dumps(line) for line in lines) + "\n")
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
        injected = {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "developer",
                "content": [{"text": f"memory: {h}/repos/other " * 50}],
            },
        }
        lines = [injected, self.codex_call(f"ls {h}/repos/shared/proj-a")]
        self.assertIsNone(self.workdir.infer(self.write(lines), self.cwd, home=self.home))

    def test_claude_transcript_and_excludes(self):
        h = str(self.home)
        lines = [{"type": "assistant", "message": {"content": f"edit {h}/repos/other/x.md"}}] * 5
        lines += [{"type": "attachment", "content": f"{h}/repos/shared/proj-a " * 50}]
        path = self.write(lines)
        self.assertEqual(self.workdir.infer(path, self.cwd, home=self.home), h + "/repos/other")
        self.assertIsNone(self.workdir.infer(path, self.cwd, exclude=[h + "/repos/other"], home=self.home))


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
        toks = self.ui.tokens("Fix GPU in /Users/a/b/c.py at 3f2a9c1d, see S3 and the 北京时间 report", words)
        self.assertIn("gpu", toks)
        self.assertIn("s3", toks)
        self.assertIn("北京时间", toks)
        self.assertNotIn("3f2a9c1d", toks)
        self.assertFalse(any("users" in t or t.endswith("py") for t in toks))

    def test_similar_memories_are_closer(self):
        docs = [
            ("VPN access policy", "The staging route keeps VPN access on the gateway."),
            ("Gateway route ACL", "The billing route on the gateway uses VPN access only."),
            ("Reply language", "Write replies in Chinese for this user."),
            ("Commit rules", "Each commit does one thing; ask before push."),
        ]
        x, vocab = self.ui.vectorize(docs)
        sim = x @ x.T
        self.assertGreater(sim[0, 1], sim[0, 2])
        self.assertGreater(sim[0, 1], sim[0, 3])

    def test_build_state(self):
        data_dir = ROOT / "ui-data"
        shutil.rmtree(data_dir, ignore_errors=True)
        for i, (desc, body) in enumerate(
            [
                ("VPN access policy", "The staging route keeps VPN access."),
                ("Gateway route ACL", "The billing route uses VPN access only."),
                ("Reply language", "Write replies in Chinese."),
                ("Commit rules", "Each commit does one thing."),
                ("Push rules", "Ask before every push and commit."),
            ]
        ):
            mdir = data_dir / "memories" / "2026" / "10"
            mdir.mkdir(parents=True, exist_ok=True)
            meta = {
                "id": f"m{i}",
                "name": f"m{i}",
                "type": "feedback",
                "scope": "global",
                "description": desc,
                "created": "2026-10-01T10:00:00+08:00",
                "source": {"tool": "cli"},
            }
            (mdir / f"m{i}.md").write_text(frontmatter.join(meta, body))
        with mock.patch.object(self.ui, "model_ready", return_value=False):  # no model in tests
            data = self.ui.build(data_dir)
        self.assertFalse(data["semantic"])
        self.assertEqual(len(data["memories"]), 5)
        m = data["memories"][0]
        self.assertTrue(m["raw"].startswith("---\nid: m"))  # the full file, for the File tab
        self.assertEqual(m["meta"]["source"], {"tool": "cli"})
        self.assertEqual(m["tool"], "cli")
        self.assertIn("no **Why:** or **How to apply:**", m["issues"])  # feedback without a reason
        self.assertIn("vpn", [k["k"] for k in by_desc_kw(data, "VPN access policy")])
        by_desc = {mm["description"]: mm for mm in data["memories"]}
        first = by_desc["VPN access policy"]["similar"][0]["i"]
        self.assertEqual(data["memories"][first]["description"], "Gateway route ACL")

    def test_keywords_prefer_names(self):
        import numpy as np

        vocab = ["actually", "choose", "routes", "gpu", "检索"]
        x = np.array([[0.9, 0.6, 0.5, 0.45, 0.4]])
        forms = {"choose": "Choose", "gpu": "GPU"}
        picks = self.ui.keyword_picks(x, vocab, forms, k=3)[0]
        self.assertEqual([vocab[j] for j in picks], ["gpu", "检索", "choose"])  # "actually" is generic

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
        body = (
            "# Task Group: Gateway\n### rollout_summary_files\n- rollout_summaries/2026-x.md (cwd=/Users/a/b)\n"
            "Keep VPN access on `staging` at /Users/a/repo/file.py, commit 3f2a9c1d."
        )
        text = self.ui.prose("Gateway policy", body)
        self.assertIn("VPN access", text)
        self.assertNotIn("rollout_summaries", text)
        self.assertNotIn("/Users", text)
        self.assertNotIn("3f2a9c1d", text)


class LintTest(unittest.TestCase):
    def setUp(self):
        from agent_memory import lint

        self.lint = lint

    def kinds(self, typ, body, desc="Short description", names=("other",)):
        m = {"type": typ, "description": desc}
        return [k for k, _ in self.lint.check(m, body, set(names))]

    def test_good_memory_passes(self):
        body = "Ask before every push.\n\n**Why:** a push once broke main.\n\n**How to apply:** ask first. See [[other]].\n"
        self.assertEqual(self.kinds("feedback", body), [])
        self.assertEqual(self.kinds("reference", "The dashboard is at example.com/d/x.\n"), [])  # Why is optional

    def test_each_rule(self):
        self.assertEqual(self.kinds("project", "# Log\n" + "x" * 1600), ["long", "heading", "reason"])
        self.assertEqual(self.kinds("user", "Fact. [[gone]]"), ["links"])
        self.assertEqual(self.kinds("user", "Fact.", desc="d" * 151), ["description"])
        self.assertEqual(self.kinds("user", "   \n"), ["empty"])
        self.assertIn(
            "no **How to apply:**",
            [
                m
                for _, m in self.lint.check(
                    {"type": "feedback", "description": "d"}, "Fact.\n\n**Why:** because.", set()
                )
            ],
        )


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
            meta = {
                "id": name,
                "name": name,
                "type": "feedback",
                "scope": "global",
                "description": desc,
                "created": "2026-10-01T10:00:00+08:00",
                "source": {"tool": "cli"},
            }
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

        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=None if body is None else json.dumps(body).encode(),
            method="GET" if body is None else "POST",
        )
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
        status, res = self.call(
            "/api/edit",
            {"id": "alpha", "base": m["hash"], "change": {"description": "alpha pref, edited", "body": "New text."}},
        )
        self.assertEqual(status, 200, res)
        edited = self.mem("alpha")
        self.assertEqual(edited["description"], "alpha pref, edited")
        self.assertIn("updated", edited["meta"])
        self.assertEqual(list(edited["meta"])[-1], "source")  # provenance stays last
        self.assertEqual(self.call("/api/edit", {"id": "alpha", "base": m["hash"], "change": {"body": "x"}})[0], 409)
        self.assertEqual(self.call("/api/undo", {"commit": res["commit"]})[0], 200)
        self.assertEqual(self.mem("alpha")["description"], "alpha pref")

    def test_create_delete_undo(self):
        status, res = self.call(
            "/api/create",
            {"type": "project", "scope": "here", "description": "new fact", "body": "N.", "place": {"path": str(ROOT)}},
        )
        self.assertEqual(status, 200, res)
        new = self.mem(res["id"])
        self.assertEqual(new["meta"]["source"]["cwd"], os.path.realpath(ROOT))
        self.assertEqual(self.call("/api/create", {"type": "project", "scope": "here", "description": "x"})[0], 400)
        status, gone = self.call("/api/delete", {"id": res["id"], "base": new["hash"]})
        self.assertEqual(status, 200)
        self.assertIsNone(self.mem(res["id"]))
        self.call("/api/undo", {"commit": gone["commit"]})
        self.assertIsNotNone(self.mem(res["id"]))
        log = subprocess.run(
            ["git", "-C", str(self.data), "log", "--format=%s", "-3"], capture_output=True, text=True
        ).stdout
        self.assertIn("memory: undo", log)

    def test_bulk_delete_is_one_commit(self):
        ids = []
        for desc in ("bulk one", "bulk two"):
            status, res = self.call(
                "/api/create", {"type": "project", "scope": "global", "description": desc, "body": "B."}
            )
            self.assertEqual(status, 200, res)
            ids.append(res["id"])
        items = [{"id": i, "base": self.mem(i)["hash"]} for i in ids]
        before = subprocess.run(
            ["git", "-C", str(self.data), "rev-list", "--count", "HEAD"], capture_output=True, text=True
        ).stdout
        status, res = self.call("/api/delete", {"items": items + [{"id": "missing-id"}]})
        self.assertEqual(status, 404)  # all or nothing
        self.assertIsNotNone(self.mem(ids[0]))
        status, res = self.call("/api/delete", {"items": items})
        self.assertEqual(status, 200, res)
        self.assertTrue(all(self.mem(i) is None for i in ids))
        after = subprocess.run(
            ["git", "-C", str(self.data), "rev-list", "--count", "HEAD"], capture_output=True, text=True
        ).stdout
        self.assertEqual(int(after) - int(before), 1)
        self.assertEqual(self.call("/api/undo", {"commit": res["commit"]})[0], 200)
        self.assertTrue(all(self.mem(i) is not None for i in ids))

    def test_insights_endpoints(self):
        status, res = self.call("/api/activity")
        self.assertEqual(status, 200)
        self.assertTrue(all(c["subject"].startswith("memory: ") for c in res["commits"]))
        globals_ = sum(m["scope"] == "global" for m in self.call("/api/state")[1]["memories"])
        status, res = self.call("/api/index-preview")
        self.assertEqual(status, 200, res)
        self.assertEqual((res["global"], res["here"]), (globals_, 0))
        self.assertIn(f"## Global ({globals_})", res["text"])
        self.assertEqual(res["chars"], len(res["text"]))
        self.assertEqual(self.call("/api/index-preview?place=nowhere")[0], 404)

    def test_settings_and_health(self):
        from agent_memory import config

        status, res = self.call("/api/settings", {"keyword_stopwords": [" Alpha ", "alpha", "beta"]})
        self.assertEqual(status, 200, res)
        self.assertEqual(res["keywordStopwords"], ["alpha", "beta"])
        self.assertEqual(config.load()["keyword_stopwords"], ["alpha", "beta"])
        self.assertEqual(self.call("/api/settings", {"keyword_stopwords": "alpha"})[0], 400)
        self.call("/api/settings", {"keyword_stopwords": []})
        status, res = self.call("/api/doctor")
        self.assertEqual(status, 200)
        self.assertTrue(res["checks"] and all({"ok", "text"} <= set(c) for c in res["checks"]))

    def test_page_routes_to_its_index(self):
        import urllib.error
        import urllib.request

        def get(path):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as r:
                    return r.status, r.headers["Content-Type"], r.read()
            except urllib.error.HTTPError as e:
                return e.code, None, e.read()

        status, ctype, page = get("/")
        self.assertEqual((status, ctype), (200, "text/html; charset=utf-8"))
        self.assertIn(b'<div id="app">', page)
        self.assertEqual(get("/insights")[2], page)  # the page routes
        self.assertEqual(get("/js/main.js")[1], "text/javascript; charset=utf-8")
        self.assertEqual(get("/app.css")[1], "text/css; charset=utf-8")
        self.assertEqual(get("/js/missing.js")[0], 404)
        self.assertEqual(get("/../ui_server.py")[2], page)  # never the file


class DemoTest(unittest.TestCase):
    def test_demo_repository_has_a_history_and_recent_dates(self):
        import datetime as dt

        from agent_memory import demo, ui_server

        data = demo.make(ROOT / "demo-data", today=dt.date(2030, 1, 10))
        memories = store.load_all(data)
        self.assertEqual(len(memories), len(list(demo.MEMORIES.rglob("*.md"))))
        self.assertTrue(max(m["created"] for m in memories).startswith("2030-01-09"))  # the newest is a day old
        commits = ui_server.UiApp(data, semantic=False).activity()["commits"]
        self.assertEqual(sum(c["added"] for c in commits), len(memories))
        self.assertEqual({c["tool"] for c in commits}, {"claude-code", "codex"})
        self.assertEqual(commits[0]["date"][:10], "2030-01-09")
        log = subprocess.run(["git", "-C", str(data), "status", "--porcelain"], capture_output=True, text=True)
        self.assertEqual(log.stdout, "")  # everything committed

    def test_demo_keeps_your_config_out_of_it(self):
        from agent_memory import config, demo

        config.save({**config.load(), "keyword_stopwords": ["mine"], "embed_model_dir": "~/models/here"})
        before = dict(os.environ)
        try:
            root = demo.prepare()
            cfg = json.loads((root / "config" / "config.json").read_text())
            self.assertEqual(cfg, {"data_dir": str(root / "data"), "embed_model_dir": "~/models/here"})
            self.assertEqual(os.environ["AGENT_MEMORY_DATA"], str(root / "data"))
        finally:
            os.environ.clear()
            os.environ.update(before)
            shutil.rmtree(root, ignore_errors=True)

    def test_demo_folder_goes_when_the_terminal_closes(self):
        import signal
        import time

        tmp = ROOT / "demo-tmp"
        tmp.mkdir(exist_ok=True)
        env = {**os.environ, "TMPDIR": str(tmp), "PYTHONPATH": str(Path(__file__).resolve().parent.parent / "src")}
        args = [sys.executable, "-m", "agent_memory", "ui", "--demo", "--no-open", "--keywords-only", "--port", "0"]
        proc = subprocess.Popen(args, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            for line in proc.stdout:
                if line.startswith("Memories:"):
                    break
            self.assertEqual(len(list(tmp.glob("agent-memory-demo-*"))), 1)
            proc.send_signal(signal.SIGHUP)
            proc.wait(timeout=10)
        finally:
            proc.kill()
        time.sleep(0.2)
        self.assertEqual(list(tmp.glob("agent-memory-demo-*")), [])


class SiteTest(unittest.TestCase):
    def test_site_builds_with_a_demo_that_matches_the_demo_memories(self):
        from agent_memory import demo

        site = Path(__file__).resolve().parent.parent / "site"
        snapshot = json.loads((site / "demo" / "snapshot.json").read_text("utf-8"))
        # saved by `scripts/site.py snapshot`; run it again after changing the demo memories
        self.assertEqual(snapshot["fingerprint"], demo.fingerprint())
        self.assertEqual(len(snapshot["state"]["memories"]), len(list(demo.MEMORIES.rglob("*.md"))))
        self.assertEqual(set(snapshot["search"]), set(snapshot["queries"]))
        out = ROOT / "site-build"
        script = site.parent / "scripts" / "site.py"
        subprocess.run([sys.executable, str(script), "build", str(out)], check=True, capture_output=True)
        for page in (
            "index.html",
            "docs.html",
            "assets/site.css",
            "demo/index.html",
            "demo/js/main.js",
        ):
            self.assertTrue((out / page).is_file(), page)
        self.assertIn('src="demo.js"', (out / "demo" / "index.html").read_text("utf-8"))
        for page in ("index.html", "docs.html"):  # every local link and image is there
            text = (out / page).read_text("utf-8")
            for ref in re.findall(r'(?:href|src|srcset)="(?![a-z]+:)([^"#?]+)', text):
                target = out / ref
                self.assertTrue(target.is_file() or (target / "index.html").is_file(), f"{page} -> {ref}")


class PageTest(unittest.TestCase):
    """The page has no build step, so check here what a bundler would: imports resolve, and every action,
    input and change an element names is one main.js handles."""

    WEBUI = Path(__file__).resolve().parent.parent / "src" / "agent_memory" / "webui"

    def scripts(self):
        return {p: p.read_text("utf-8") for p in (self.WEBUI / "js").rglob("*.js")}

    def test_imports_resolve(self):
        import re

        for path, text in self.scripts().items():
            for target in re.findall(r'^import .*? from "(\.[^"]+)";$', text, re.M):
                self.assertTrue((path.parent / target).resolve().is_file(), f"{path.name} imports {target}")
            for name in re.findall(r"^import \{ ([^}]+) \} from", text, re.M):
                self.assertTrue(name.strip(), path.name)
        index = (self.WEBUI / "index.html").read_text("utf-8")
        for ref in re.findall(r'(?:src|href)="([^":]+)"', index):
            self.assertTrue((self.WEBUI / ref).is_file(), ref)

    def test_every_named_handler_exists(self):
        import re

        main = (self.WEBUI / "js" / "main.js").read_text("utf-8")
        tables = {
            "act": re.search(r"const ACTIONS = \{(.*?)\n\};", main, re.S).group(1),
            "input": re.search(r"const INPUTS = \{(.*?)\n\};", main, re.S).group(1),
            "change": re.search(r"const CHANGES = \{(.*?)\n\};", main, re.S).group(1),
        }
        handled = {kind: set(re.findall(r"^\s+(\w+):", body, re.M)) for kind, body in tables.items()}
        views = "\n".join(self.scripts().values())
        # names given straight to an element, or to the helpers in views/ui.js that pass them on
        helpers = {
            "act": [
                r'iconButton\("[^"]+", "[^"]+", "(\w+)"',
                r'toggle\([^,]+, "[^"]+", "(\w+)"\)',
                r'checkbox\([^,]+, "[^"]+", "(\w+)"',
                r'segmented\(.*?(?:\]|\)\)), "(\w+)"',
            ],
            "input": [],
            "change": [r'select\(.*?(?:\]|placeItems), "(\w+)"'],
        }
        for kind in ("act", "input", "change"):
            used = set(re.findall(rf'data-{kind}="(\w+)', views)) | set(re.findall(rf'"data-{kind}": "(\w+)"', views))
            for pattern in helpers[kind]:
                used |= set(re.findall(pattern, views))
            self.assertTrue(used, kind)
            missing = sorted(
                name for name in used if name not in handled[kind] and not (kind == "input" and name == "draft")
            )
            self.assertFalse(missing, f"data-{kind} with no handler: {missing}")


class RemoteSettingTest(unittest.TestCase):
    def test_connect_change_and_disconnect_a_remote(self):
        from agent_memory import gitsync, ui_server

        data, bare = ROOT / "remote-setting-data", ROOT / "remote-setting.git"
        for path in (data, bare):
            shutil.rmtree(path, ignore_errors=True)
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
        install.init_data(data)
        app = ui_server.UiApp(data, semantic=False)
        self.assertIsNone(app.settings()["remote"])

        with self.assertRaises(ui_server.ApiError):  # never something git would read as an option
            app.set_remote({"url": "--upload-pack=touch x"})
        r = app.set_remote({"url": str(bare)})  # empty: this repository is pushed to it
        self.assertTrue(r["ok"], r["message"])
        self.assertEqual(r["settings"]["remoteUrl"], str(bare))
        self.assertEqual(gitsync.git(bare, "rev-parse", "main").stdout, gitsync.git(data, "rev-parse", "HEAD").stdout)
        self.assertEqual(app.sync_status(), {"remote": True, "ahead": 0})

        r = app.set_remote({"url": None})
        self.assertTrue(r["ok"])
        self.assertFalse(gitsync.has_remote(data))
        r = app.set_remote({"url": str(bare)})  # already has this branch: linked and synced
        self.assertTrue(r["ok"], r["message"])
        self.assertEqual(r["message"], "Connected and synced.")


class UiSyncStatusTest(unittest.TestCase):
    def test_finished_push_clears_not_pushed(self):
        from agent_memory import gitsync, ui, ui_server

        data, bare = ROOT / "ui-sync-data", ROOT / "ui-sync.git"
        for path in (data, bare):
            shutil.rmtree(path, ignore_errors=True)
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
        install.init_data(data)
        gitsync.git(data, "remote", "add", "origin", str(bare))
        gitsync.git(data, "push", "-q", "-u", "origin", "main")
        path = data / "memories" / "2026" / "10" / "fresh.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\nid: fresh\ntype: user\nscope: global\ndescription: fresh\n---\nfresh\n")
        gitsync.commit(data, "memory: fresh")

        with mock.patch.object(ui, "model_ready", return_value=False):
            app = ui_server.UiApp(data, semantic=False)
            self.assertEqual(app.current()["sync"], {"remote": True, "ahead": 1})
            gitsync.git(data, "push", "-q")  # what the background push does after a commit
            self.assertEqual(app.current()["sync"], {"remote": True, "ahead": 0})


class UpdateTest(unittest.TestCase):
    def setUp(self):
        from agent_memory import config, update

        self.update = update
        (config.CONFIG_DIR / update.CACHE_NAME).unlink(missing_ok=True)
        config.save({})

    def test_versions_compare_as_numbers(self):
        newer = self.update.newer
        self.assertTrue(newer("0.1.10", "0.1.9"))
        self.assertTrue(newer("0.2.0", "0.1.9"))
        self.assertTrue(newer("0.2.0", "0.2.0rc1"))
        self.assertFalse(newer("0.1.3", "0.1.3"))
        self.assertFalse(newer("0.1.2", "0.1.3"))
        self.assertFalse(newer(None, "0.1.3"))

    def test_check_is_cached_and_can_be_turned_off(self):
        from agent_memory import config

        u = self.update
        with (
            mock.patch.object(u, "current", return_value="0.1.3"),
            mock.patch.object(u, "how_installed", return_value="uv-tool"),
            mock.patch.object(u, "fetch_latest", return_value="0.1.4") as fetch,
        ):
            first = u.status()
            self.assertEqual((first["latest"], first["available"], first["oneClick"]), ("0.1.4", True, True))
            u.status()
            self.assertEqual(fetch.call_count, 1)  # kept for a day
            config.save({"check_updates": False})
            (config.CONFIG_DIR / u.CACHE_NAME).unlink()
            off = u.status()
            self.assertEqual((off["latest"], off["auto"], fetch.call_count), (None, False, 1))
            self.assertEqual(u.status(force=True)["latest"], "0.1.4")  # Check now still asks
            self.assertEqual(fetch.call_count, 2)

    def test_upgrade_needs_a_uv_tool_install(self):
        with mock.patch.object(self.update, "how_installed", return_value="other"):
            self.assertFalse(self.update.upgrade()["ok"])

    def test_upgrade_runs_uv_then_mem_install(self):
        u = self.update
        done = lambda out="": subprocess.CompletedProcess([], 0, out, "")  # noqa: E731
        calls = []

        def run(cmd, **kw):
            calls.append(cmd)
            return done("0.1.4\n") if "-c" in cmd else done()

        with (
            mock.patch.object(u, "how_installed", return_value="uv-tool"),
            mock.patch.object(u, "current", return_value="0.1.3"),
            mock.patch.object(u.shutil, "which", return_value="/bin/uv"),
            mock.patch.object(u.subprocess, "run", side_effect=run),
        ):
            res = u.upgrade()
        self.assertEqual((res["ok"], res["from"], res["to"], res["changed"]), (True, "0.1.3", "0.1.4", True))
        self.assertEqual(calls[0], ["/bin/uv", "tool", "upgrade", u.PACKAGE])
        self.assertEqual(calls[-1][1:], ["-m", "agent_memory", "install"])

    def test_a_pinned_install_is_installed_again_without_the_pin(self):
        u = self.update
        env = ROOT / "uv-tool-env"
        env.mkdir(exist_ok=True)
        receipt = env / "uv-receipt.toml"

        def args(text=None):
            receipt.unlink(missing_ok=True)
            if text:
                receipt.write_text(text)
            with mock.patch.object(u.sys, "prefix", str(env)):
                return u.upgrade_args()

        mem = 'entrypoints = [{ name = "mem", install-path = "/bin/mem", from = "agent-memory-git" }]\n'
        plain = '[tool]\nrequirements = [{ name = "agent-memory-git", extras = ["ui"] }]\n' + mem
        pinned = (
            '[tool]\nrequirements = [{ name = "agent-memory-git", extras = ["ui"], specifier = "==0.1.3" },'
            ' { name = "extra-pkg", specifier = ">=1" }]\npython = "3.11"\n' + mem
        )
        upgrade = ["tool", "upgrade", u.PACKAGE]
        self.assertEqual(args(plain), upgrade)
        self.assertEqual(
            args(pinned),
            ["tool", "install", "--upgrade", "agent-memory-git[ui]", "--python", "3.11", "--with", "extra-pkg>=1"],
        )
        # what a plain install could lose stays with uv tool upgrade, which then reports the pin
        self.assertEqual(args(pinned + '[tool.options]\nindex-url = "https://example.org/simple"\n'), upgrade)
        self.assertEqual(args(), upgrade)

    def test_an_update_that_installs_nothing_says_so(self):
        from agent_memory import config

        u = self.update
        calls = []

        def run(cmd, **kw):
            calls.append(cmd)
            return subprocess.CompletedProcess([], 0, "0.1.3\n" if "-c" in cmd else "Nothing to upgrade\n", "")

        def upgrade(latest):
            (config.CONFIG_DIR / u.CACHE_NAME).write_text(json.dumps({"latest": latest}))
            with (
                mock.patch.object(u, "how_installed", return_value="uv-tool"),
                mock.patch.object(u, "current", return_value="0.1.3"),
                mock.patch.object(u.shutil, "which", return_value="/bin/uv"),
                mock.patch.object(u.subprocess, "run", side_effect=run),
            ):
                return u.upgrade()

        missed = upgrade("0.1.4")
        self.assertEqual((missed["ok"], missed["changed"], missed["to"]), (False, False, "0.1.3"))
        self.assertIn("0.1.4", missed["error"])
        self.assertIn("Nothing to upgrade", missed["log"])
        current = upgrade("0.1.3")
        self.assertEqual((current["ok"], current["changed"], current["error"]), (True, False, None))
        self.assertNotIn(["-m", "agent_memory", "install"], [c[1:] for c in calls])  # nothing to refresh

    def test_restart_keeps_the_token_and_stops_serving(self):
        import threading
        import urllib.request

        from agent_memory import ui, ui_server

        data = ROOT / "restart-data"
        install.init_data(data)
        os.environ[ui_server.RESTART_TOKEN] = "kept-token"
        with mock.patch.object(ui, "model_ready", return_value=False):
            server = ui_server.make_server(data, port=0, semantic=False)
        self.assertEqual(server.token, "kept-token")
        self.assertNotIn(ui_server.RESTART_TOKEN, os.environ)
        loop = threading.Thread(target=server.serve_forever, daemon=True)
        loop.start()
        req = urllib.request.Request(
            f"http://127.0.0.1:{server.server_address[1]}/api/restart",
            data=b"{}",
            headers={"X-Mem-Token": "kept-token", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as r:
            self.assertEqual(json.loads(r.read()), {"restarting": True})
        loop.join(5)
        self.assertFalse(loop.is_alive())
        self.assertTrue(server.restart)
        server.server_close()


class DoctorTest(unittest.TestCase):
    def test_only_recent_hook_errors_count(self):
        import datetime as dt

        log = (
            "2026-10-01T10:00:00+08:00 ERROR in hook stop (codex):\nTraceback ...\n"
            "2026-10-14T09:00:00+08:00 flush claude-code-x: promoted=1 committed=True\n"
            "2026-10-14T10:00:00+08:00 ERROR in ui /api/state:\nConnectionResetError\n"
            "2026-10-14T11:00:00+08:00 ERROR in hook session-start (claude-code):\nTraceback ...\n"
        )
        now = dt.datetime.fromisoformat("2026-10-15T12:00:00+08:00")
        self.assertEqual(
            install.recent_hook_errors(log, now), ["2026-10-14T11:00:00+08:00 hook session-start (claude-code)"]
        )
        self.assertEqual(install.recent_hook_errors(log, now + dt.timedelta(days=30)), [])

    def test_a_data_repository_without_a_remote_is_fine(self):
        from agent_memory import config

        data = ROOT / "doctor-no-remote"
        install.init_data(data)
        with mock.patch.object(config, "data_dir", return_value=data):
            checks = dict((text, ok) for ok, text in install.doctor_checks())
        self.assertIs(checks.get("no remote: memories stay on this machine"), True)

    def test_doctor_exits_non_zero_when_a_check_fails(self):
        from agent_memory import cli

        for checks, code in (([(True, "a"), (True, "b")], 0), ([(True, "a"), (False, "b")], 1)):
            with (
                mock.patch.object(install, "doctor_checks", return_value=checks),
                mock.patch("sys.stdout", io.StringIO()),
            ):
                self.assertEqual(cli.main(["doctor"]), code)


class PackagingTest(unittest.TestCase):
    def test_hooks_run_the_package_with_python_m(self):
        from agent_memory import config

        cmd = config.mem_command()
        self.assertTrue(Path(cmd[0]).samefile(sys.executable))
        self.assertEqual(cmd[1:], ["-m", "agent_memory"])

    def test_hooks_name_the_python_beside_the_interpreter_when_it_is_the_same_file(self):
        from agent_memory import config

        venv, other, bare = (ROOT / "bins" / d for d in ("venv", "other", "bare"))
        for d in (venv, other, bare):
            d.mkdir(parents=True)
            (d / "python3.11").write_text("")
        (venv / "python").symlink_to("python3.11")  # how a venv lays them out
        (venv / "python3").symlink_to("python")
        (other / "python").write_text("")  # a different interpreter
        cases = {venv / "python3": venv / "python", venv / "python": venv / "python"}
        cases |= {other / "python3.11": other / "python3.11", bare / "python3.11": bare / "python3.11"}
        for started, expected in cases.items():
            with mock.patch.object(config.sys, "executable", str(started)):
                self.assertEqual(config.mem_command()[0], str(expected), started)

    def test_protocol_ships_inside_the_package(self):
        from agent_memory import config

        self.assertEqual(config.PROTOCOL.parent, config.PACKAGE_DIR)
        self.assertIn("# Shared memory", config.PROTOCOL.read_text())


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


CONFIG_TOML = """model = "m"

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
"""

HOOKS_JSON = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "otter Stop"}]}]}}

SETTINGS = {
    "permissions": {"allow": ["Bash(ls:*)"]},
    "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "other"}]}]},
}


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
        files = [
            install.CLAUDE_DIR / "settings.json",
            install.CLAUDE_DIR / "CLAUDE.md",
            install.CODEX_DIR / "config.toml",
            install.CODEX_DIR / "hooks.json",
            install.CODEX_DIR / "AGENTS.md",
        ]
        return {str(f): f.read_text() if f.exists() else None for f in files}

    def test_install_uninstall_round_trip(self):
        before = self.snapshot()
        rc = ROOT / "zshrc"
        rc.write_text("export FOO=1\n")
        rc_before = rc.read_text()
        with (
            mock.patch.object(install, "LOCAL_BIN", ROOT / "bin" / "mem"),
            mock.patch.object(install, "_login_path", return_value=["/usr/bin"]),
            mock.patch.object(install, "_rc_file", return_value=rc),
            mock.patch("sys.stdout", io.StringIO()),
        ):
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
            from agent_memory import config

            self.assertIn(f"@{config.PROTOCOL_COPY}", mid[str(install.CLAUDE_DIR / "CLAUDE.md")])
            self.assertEqual(config.PROTOCOL_COPY.read_text(), config.PROTOCOL.read_text())
            hook = settings["hooks"]["SessionStart"][-1]["hooks"][0]["command"]
            self.assertTrue(hook.endswith("hook session-start --tool claude-code"), hook)
            self.assertIn(" -m agent_memory hook ", hook)
            self.assertIn(install.PATH_LINE, rc.read_text())

            install.install()  # idempotent
            self.assertEqual(self.snapshot(), mid)

            # tools keep writing their own state while we are installed
            cfg = install.CODEX_DIR / "config.toml"
            cfg.write_text(cfg.read_text() + '\n[projects."/new"]\ntrust_level = "trusted"\n')

            # an older install recorded ~/.local/bin/mem; now that uv owns it, it must survive
            live = ROOT / "bin" / "mem"
            live.parent.mkdir(parents=True, exist_ok=True)
            (ROOT / "uv-mem").write_text("#!/bin/sh\n")
            live.unlink(missing_ok=True)
            live.symlink_to(ROOT / "uv-mem")
            st = json.loads(install.STATE_FILE.read_text())
            install.STATE_FILE.write_text(json.dumps({**st, "local_bin": str(live)}))

            install.uninstall()
            self.assertTrue(live.is_symlink())
        after = self.snapshot()
        self.assertFalse(config.PROTOCOL_COPY.exists())
        self.assertEqual(rc.read_text(), rc_before)
        for path, text in before.items():
            if path.endswith("config.toml"):
                self.assertEqual(after[path], text + '\n[projects."/new"]\ntrust_level = "trusted"\n')
            else:
                self.assertEqual(after[path], text, path)


if __name__ == "__main__":
    unittest.main()
