"""Wiring agent-memory into Claude Code and Codex, and taking it out again.

Every change is recorded in install-state.json so that uninstall reverts
exactly what install added, without rewriting files wholesale: both tools
keep writing their own state into these files while we are installed.
"""

import copy
import datetime as _dt
import difflib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from . import config, gitsync
from .util import HOME

STATE_FILE = config.CONFIG_DIR / "install-state.json"
BEGIN = "<!-- agent-memory:begin -->"
END = "<!-- agent-memory:end -->"
MISSING = "__missing__"

CLAUDE_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR", HOME / ".claude"))
CODEX_DIR = Path(os.environ.get("CODEX_HOME", HOME / ".codex"))
LOCAL_BIN = HOME / ".local" / "bin" / "mem"

SH_BEGIN = "# >>> agent-memory >>>"
SH_END = "# <<< agent-memory <<<"
PATH_LINE = 'export PATH="$HOME/.local/bin:$PATH"'

HOOK_EVENTS = [("SessionStart", "session-start", 15),
               ("Stop", "stop", 15),
               ("SessionEnd", "session-end", 3)]  # Codex clamps SessionEnd to 3s


# ---------------------------------------------------------------- helpers

def hook_command(event, tool):
    return " ".join(shlex.quote(a) for a in config.mem_command()) + f" hook {event} --tool {tool}"


def _is_ours(group):
    return any(("agent-memory" in h.get("command", "") or "agent_memory" in h.get("command", ""))
               and " hook " in h.get("command", "")
               for h in group.get("hooks", []))


def _home_rel(path):
    path = Path(path)
    try:
        return "~/" + path.relative_to(HOME).as_posix()
    except ValueError:
        return "/" + path.as_posix()  # Claude Code reads "//abs" as an absolute path


def _read(path):
    try:
        return Path(path).read_text("utf-8")
    except FileNotFoundError:
        return None


def _block(text, inner, begin=BEGIN, end_mark=END):
    """Insert or replace our marked block in a file's text."""
    text = text or ""
    block = f"{begin}\n{inner.rstrip()}\n{end_mark}\n"
    if begin in text and end_mark in text:
        start, end = text.index(begin), text.index(end_mark) + len(end_mark)
        return text[:start] + block.rstrip("\n") + text[end:]
    sep = "" if not text or text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    return text + sep + block


def _unblock(text, begin=BEGIN, end_mark=END):
    if not text or begin not in text or end_mark not in text:
        return text
    start, end = text.index(begin), text.index(end_mark) + len(end_mark)
    out = text[:start].rstrip("\n") + text[end:].lstrip("\n")
    out = out.strip("\n")
    return out + "\n" if out else ""


def _toml_section(text, section):
    """(start, end) line indexes of a [section] body, or None."""
    lines = text.split("\n")
    header = re.compile(r"^\s*\[" + re.escape(section) + r"\]\s*(#.*)?$")
    for i, l in enumerate(lines):
        if header.match(l):
            j = i + 1
            while j < len(lines) and not re.match(r"^\s*\[", lines[j]):
                j += 1
            return i, j
    return None


def toml_get(text, section, key):
    try:
        return tomllib.loads(text).get(section, {}).get(key, MISSING)
    except tomllib.TOMLDecodeError:
        return MISSING


def toml_set(text, section, key, literal):
    """Set `key = literal` in [section] (creating either) with minimal edits."""
    lines = text.split("\n")
    span = _toml_section(text, section)
    pattern = re.compile(r"^\s*" + re.escape(key) + r"\s*=")
    if span:
        i, j = span
        for k in range(i + 1, j):
            if pattern.match(lines[k]):
                lines[k] = f"{key} = {literal}"
                return "\n".join(lines)
        lines.insert(i + 1, f"{key} = {literal}")
        return "\n".join(lines)
    if lines and lines[-1] == "":
        lines.pop()
    lines += ["", f"[{section}]", f"{key} = {literal}", ""]
    return "\n".join(lines)


def toml_unset(text, section, key):
    span = _toml_section(text, section)
    if not span:
        return text
    lines = text.split("\n")
    i, j = span
    pattern = re.compile(r"^\s*" + re.escape(key) + r"\s*=")
    lines = [l for n, l in enumerate(lines) if not (i < n < j and pattern.match(l))]
    span = _toml_section("\n".join(lines), section)
    if span:  # drop the section if we emptied it
        i, j = span
        if all(not l.strip() for l in lines[i + 1:j]):
            del lines[i:j]
    return "\n".join(lines)


def _toml_literal(value):
    return json.dumps(value) if not isinstance(value, bool) else ("true" if value else "false")


def _login_path():
    """PATH of a fresh login shell, unaffected by whatever launched us."""
    shell = os.environ.get("SHELL", "/bin/zsh")
    env = {"HOME": str(HOME), "USER": os.environ.get("USER", ""), "SHELL": shell, "TERM": "dumb"}
    try:
        r = subprocess.run([shell, "-lic", 'printf "__P__%s__P__" "$PATH"'], env=env,
                           capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"__P__(.*?)__P__", r.stdout, re.S)
    return m.group(1).split(":") if m else None


def _rc_file():
    shell = os.path.basename(os.environ.get("SHELL", "zsh"))
    return HOME / (".bashrc" if shell == "bash" else ".zshrc")


def _path_plan(plan, state):
    """Make `mem` reachable from a new terminal when ~/.local/bin is not on PATH."""
    path = _login_path()
    if path is None or str(LOCAL_BIN.parent) in path:
        return
    rc = _rc_file()
    plan.edit(rc, _block(_read(rc), PATH_LINE, SH_BEGIN, SH_END))
    state["shell_rc"] = str(rc)


# ---------------------------------------------------------------- planning

class Plan:
    def __init__(self):
        self.files = {}          # path -> (old_text or None, new_text or None)
        self.state = {}

    def edit(self, path, new_text):
        path = Path(path)
        old = self.files[path][0] if path in self.files else _read(path)
        self.files[path] = (old, new_text)

    def show(self):
        for path, (old, new) in self.files.items():
            if old == new:
                continue
            a = (old or "").splitlines(keepends=True)
            b = (new or "").splitlines(keepends=True)
            label = "(new file)" if old is None else "(delete)" if new is None else ""
            print(f"=== {path} {label}")
            sys.stdout.writelines(difflib.unified_diff(a, b, "before", "after", n=1))
            print()

    def apply(self, backup_dir):
        backup_dir.mkdir(parents=True, exist_ok=True)
        for path, (old, new) in self.files.items():
            if old == new:
                continue
            if old is not None:
                dest = backup_dir / str(path).lstrip("/").replace("/", "__")
                dest.write_text(old, "utf-8")
            if new is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(new, "utf-8")


def _claude_plan(plan, data_dir, state):
    settings_path = CLAUDE_DIR / "settings.json"
    text = _read(settings_path)
    settings = json.loads(text) if text else {}
    new = copy.deepcopy(settings)

    state.setdefault("claude.autoMemoryEnabled", settings.get("autoMemoryEnabled", MISSING))
    new["autoMemoryEnabled"] = False

    hooks = new.setdefault("hooks", {})
    for event, name, timeout in HOOK_EVENTS:
        groups = [g for g in hooks.get(event, []) if not _is_ours(g)]
        groups.append({"hooks": [{"type": "command", "command": hook_command(name, "claude-code"),
                                  "timeout": timeout}]})
        hooks[event] = groups

    data = _home_rel(data_dir)
    rules = [f"Read({data}/**)", f"Edit({data}/**)",
             f"Bash({config.BIN} search:*)", f"Bash({config.BIN} list:*)",
             f"Bash({config.BIN} show:*)",
             "Bash(mem search:*)", "Bash(mem list:*)", "Bash(mem show:*)"]
    allow = new.setdefault("permissions", {}).setdefault("allow", [])
    added = [r for r in rules if r not in allow]
    allow.extend(added)
    state["claude.permissions"] = sorted(set(state.get("claude.permissions", [])) | set(added))
    plan.edit(settings_path, json.dumps(new, indent=2, ensure_ascii=False) + "\n")

    # Import a copy in the config folder: its path stays the same whichever way the package is
    # installed or upgraded, and `mem install` refreshes it.
    plan.edit(config.PROTOCOL_COPY, config.PROTOCOL.read_text("utf-8"))
    claude_md = CLAUDE_DIR / "CLAUDE.md"
    plan.edit(claude_md, _block(_read(claude_md), f"@{config.PROTOCOL_COPY}"))


def _codex_plan(plan, data_dir, state):
    hooks_path = CODEX_DIR / "hooks.json"
    text = _read(hooks_path)
    doc = json.loads(text) if text else {}
    new = copy.deepcopy(doc)
    hooks = new.setdefault("hooks", {})
    for event, name, timeout in HOOK_EVENTS:
        groups = [g for g in hooks.get(event, []) if not _is_ours(g)]
        handler = {"type": "command", "command": hook_command(name, "codex"), "timeout": timeout}
        if event == "SessionStart":
            handler["statusMessage"] = "Loading shared memory"
            handler["additionalContextLimit"] = 0  # keep the index inline, never spill to disk
        groups.append({"hooks": [handler]})
        hooks[event] = groups
    plan.edit(hooks_path, json.dumps(new, indent=2, ensure_ascii=False) + "\n")

    toml_path = CODEX_DIR / "config.toml"
    toml = _read(toml_path) or ""
    for key in ("generate_memories", "use_memories"):
        state.setdefault(f"codex.memories.{key}", toml_get(toml, "memories", key))
        toml = toml_set(toml, "memories", key, "false")
    roots = toml_get(toml, "sandbox_workspace_write", "writable_roots")
    roots = [] if roots == MISSING else list(roots)
    state.setdefault("codex.writable_roots.had_key", toml_get(
        _read(toml_path) or "", "sandbox_workspace_write", "writable_roots") != MISSING)
    if str(data_dir) not in roots:
        roots.append(str(data_dir))
        state["codex.writable_root"] = str(data_dir)
    toml = toml_set(toml, "sandbox_workspace_write", "writable_roots", json.dumps(roots))
    tomllib.loads(toml)  # refuse to write a config Codex could not parse
    plan.edit(toml_path, toml)

    agents_md = CODEX_DIR / "AGENTS.md"
    protocol = config.PROTOCOL.read_text("utf-8")
    plan.edit(agents_md, _block(_read(agents_md), protocol))


# ---------------------------------------------------------------- commands

def _load_state():
    try:
        return json.loads(STATE_FILE.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def init_data(data_dir):
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "memories").mkdir(exist_ok=True)
    gi = data_dir / ".gitignore"
    if not gi.exists():
        gi.write_text("staging/\n.cache/\n.DS_Store\n", "utf-8")
    readme = data_dir / "README.md"
    if not readme.exists():
        readme.write_text(
            "# agent-memory data\n\n"
            "One Markdown file per memory under `memories/YYYY/MM/`, written by Claude Code and\n"
            "Codex through the agent-memory hooks. Edit or delete files freely; every change is\n"
            "a git commit.\n", "utf-8")
    if not (data_dir / ".git").exists():
        gitsync.git(data_dir, "init", "-q", "-b", "main")
    gitsync.git(data_dir, "add", "-A")
    gitsync.git(data_dir, "-c", "commit.gpgsign=false", "commit", "-q", "--no-verify",
                "-m", "Initialize memory repository")
    cfg = config.load()
    cfg["data_dir"] = str(data_dir)
    config.save(cfg)
    print(f"data repository ready at {data_dir}; config written to {config.CONFIG_FILE}")


def install(dry_run=False, claude=True, codex=True):
    data_dir = config.data_dir()
    if not data_dir or not (data_dir / ".git").exists():
        sys.exit("run `mem init <data-dir>` first")
    state = _load_state()
    plan = Plan()
    if claude and CLAUDE_DIR.is_dir():
        _claude_plan(plan, data_dir, state)
    if codex and CODEX_DIR.is_dir():
        _codex_plan(plan, data_dir, state)
    _path_plan(plan, state)

    plan.show()
    link_ok = LOCAL_BIN.is_symlink() and LOCAL_BIN.resolve() == config.BIN.resolve()
    if not link_ok:
        print(f"=== {LOCAL_BIN} -> {config.BIN} (symlink)\n")
    if dry_run:
        print("dry run: nothing changed")
        return

    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    plan.apply(config.CONFIG_DIR / "backups" / stamp)
    if not link_ok and not LOCAL_BIN.exists():
        LOCAL_BIN.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_BIN.symlink_to(config.BIN)
        state["local_bin"] = str(LOCAL_BIN)
    state["installed_at"] = stamp
    state["claude"] = state.get("claude") or (claude and CLAUDE_DIR.is_dir())
    state["codex"] = state.get("codex") or (codex and CODEX_DIR.is_dir())
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print(f"installed; backups in {config.CONFIG_DIR / 'backups' / stamp}")
    if state.get("codex"):
        print("Codex: open /hooks in Codex once and trust the three agent-memory hooks.")


def uninstall(dry_run=False):
    state = _load_state()
    if not state:
        sys.exit("nothing to uninstall (no install-state.json)")
    plan = Plan()

    if state.get("claude"):
        path = CLAUDE_DIR / "settings.json"
        text = _read(path)
        if text:
            s = json.loads(text)
            prev = state.get("claude.autoMemoryEnabled", MISSING)
            if prev == MISSING:
                s.pop("autoMemoryEnabled", None)
            else:
                s["autoMemoryEnabled"] = prev
            for event, _, _ in HOOK_EVENTS:
                groups = [g for g in s.get("hooks", {}).get(event, []) if not _is_ours(g)]
                if groups:
                    s["hooks"][event] = groups
                else:
                    s.get("hooks", {}).pop(event, None)
            if "hooks" in s and not s["hooks"]:
                del s["hooks"]
            ours = set(state.get("claude.permissions", []))
            allow = s.get("permissions", {}).get("allow")
            if allow is not None:
                s["permissions"]["allow"] = [r for r in allow if r not in ours]
            plan.edit(path, json.dumps(s, indent=2, ensure_ascii=False) + "\n")
        md = CLAUDE_DIR / "CLAUDE.md"
        text = _read(md)
        if text is not None:
            out = _unblock(text)
            plan.edit(md, out if out else None)
        if config.PROTOCOL_COPY.exists():
            plan.edit(config.PROTOCOL_COPY, None)

    if state.get("codex"):
        path = CODEX_DIR / "hooks.json"
        text = _read(path)
        if text:
            doc = json.loads(text)
            for event, _, _ in HOOK_EVENTS:
                groups = [g for g in doc.get("hooks", {}).get(event, []) if not _is_ours(g)]
                if groups:
                    doc["hooks"][event] = groups
                else:
                    doc.get("hooks", {}).pop(event, None)
            plan.edit(path, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        path = CODEX_DIR / "config.toml"
        toml = _read(path) or ""
        for key in ("generate_memories", "use_memories"):
            prev = state.get(f"codex.memories.{key}", MISSING)
            toml = toml_unset(toml, "memories", key) if prev == MISSING else \
                toml_set(toml, "memories", key, _toml_literal(prev))
        root = state.get("codex.writable_root")
        roots = toml_get(toml, "sandbox_workspace_write", "writable_roots")
        if root and roots != MISSING:
            roots = [r for r in roots if r != root]
            if roots or state.get("codex.writable_roots.had_key"):
                toml = toml_set(toml, "sandbox_workspace_write", "writable_roots", json.dumps(roots))
            else:
                toml = toml_unset(toml, "sandbox_workspace_write", "writable_roots")
        tomllib.loads(toml)
        plan.edit(path, toml)
        md = CODEX_DIR / "AGENTS.md"
        text = _read(md)
        if text is not None:
            plan.edit(md, _unblock(text))  # keep the file: it existed (empty) before

    rc = state.get("shell_rc")
    if rc:
        text = _read(rc)
        if text is not None:
            plan.edit(Path(rc), _unblock(text, SH_BEGIN, SH_END))

    plan.show()
    local = state.get("local_bin")
    if local:
        print(f"=== remove symlink {local}\n")
    if dry_run:
        print("dry run: nothing changed")
        return
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    plan.apply(config.CONFIG_DIR / "backups" / f"uninstall-{stamp}")
    if local and Path(local).is_symlink():
        Path(local).unlink()
    STATE_FILE.rename(STATE_FILE.with_name(f"install-state.uninstalled-{stamp}.json"))
    print("uninstalled. Native memory settings restored; the data repository is untouched.")


def doctor():
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(("ok   " if cond else "FAIL ") + msg)
        ok &= bool(cond)

    data = config.data_dir()
    check(data and (data / ".git").exists(), f"data repository: {data}")
    state = _load_state()
    check(bool(state), f"install state: {STATE_FILE}")
    if state.get("claude"):
        s = json.loads(_read(CLAUDE_DIR / "settings.json") or "{}")
        check(s.get("autoMemoryEnabled") is False, "Claude auto memory disabled")
        for event, _, _ in HOOK_EVENTS:
            check(any(_is_ours(g) for g in s.get("hooks", {}).get(event, [])), f"Claude {event} hook")
        check(f"@{config.PROTOCOL_COPY}" in (_read(CLAUDE_DIR / "CLAUDE.md") or ""), "Claude CLAUDE.md imports PROTOCOL.md")
        check(_read(config.PROTOCOL_COPY) == config.PROTOCOL.read_text("utf-8"),
              "Claude's PROTOCOL.md copy is current (else run `mem install`)")
    if state.get("codex"):
        doc = json.loads(_read(CODEX_DIR / "hooks.json") or "{}")
        for event, _, _ in HOOK_EVENTS:
            check(any(_is_ours(g) for g in doc.get("hooks", {}).get(event, [])), f"Codex {event} hook")
        toml = _read(CODEX_DIR / "config.toml") or ""
        check(toml_get(toml, "memories", "use_memories") is False, "Codex native memories disabled")
        check(config.PROTOCOL.read_text("utf-8").rstrip() in (_read(CODEX_DIR / "AGENTS.md") or ""),
              "Codex AGENTS.md has the current protocol (else run `mem install`)")
    path = _login_path()
    if path is not None:
        check(str(LOCAL_BIN.parent) in path or SH_BEGIN in (_read(_rc_file()) or ""),
              f"`mem` on a new terminal's PATH ({LOCAL_BIN.parent})")
    if data:
        check(gitsync.has_remote(data), "data repository has a remote (optional)")
        staged = list((data / "staging").glob("*/*.md")) if (data / "staging").exists() else []
        check(not staged, f"no stuck staged files ({len(staged)})")
        logf = data / ".cache" / "agent-memory.log"
        errors = (_read(logf) or "").count("ERROR")
        check(errors == 0, f"hook errors in {logf}: {errors}")
    return 0 if ok else 1
