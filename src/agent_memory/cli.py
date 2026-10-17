"""`mem` command line."""

import argparse
import atexit
import os
import shutil
import sys
from pathlib import Path

from . import capture, config, frontmatter, gitsync, hooks, select, store
from .context import detect
from .util import SCOPES, TYPES, atomic_write, slugify


def _data():
    d = config.data_dir()
    if not d or not (d / ".git").exists():
        sys.exit("agent-memory is not set up: run `mem init <data-dir>` first")
    return d


def _filter(memories, args, ctx):
    globals_, here = select.visible(memories, ctx, include_all=getattr(args, "all", False))
    if getattr(args, "glob", False):
        items = globals_
    elif getattr(args, "here", False):
        items = here
    else:
        items = globals_ + here
    if getattr(args, "type", None):
        items = [m for m in items if m["type"] == args.type]
    return items


def cmd_list(args):
    data = _data()
    ctx = detect(args.cwd)
    for m in _filter(store.load_all(data), args, ctx)[: args.limit]:
        print(select.line(m))


def cmd_search(args):
    data = _data()
    ctx = detect(args.cwd)
    terms = [t.lower() for t in args.terms]
    mdir = store.memories_dir(data)
    hits = 0
    for m in _filter(store.load_all(data), args, ctx):
        try:
            meta, body = store.read(mdir / m["rel"])
        except OSError:
            continue
        hay = " ".join([m["name"], m["description"], body]).lower()
        if all(t in hay for t in terms):
            print(select.line(m))
            for raw in body.splitlines():
                if any(t in raw.lower() for t in terms):
                    print(f"    {raw.strip()[:200]}")
                    break
            hits += 1
            if hits >= args.limit:
                break
    if not hits:
        print("no matches" + ("" if args.all else " (try --all for other locations)"))


def cmd_show(args):
    data = _data()
    m = store.find(data, args.key)
    if not m:
        sys.exit(f"no memory {args.key!r}")
    path = store.memories_dir(data) / m["rel"]
    print(f"# {path}")
    print(path.read_text("utf-8"), end="")


def cmd_index(args):
    data = _data()
    ctx = detect(args.cwd)
    paths = {"memories": str(store.memories_dir(data)), "staging": "(per session)", "mem": str(config.BIN)}
    text = select.render(store.load_all(data), ctx, paths)
    print(text, end="")
    print(f"\n[{len(text)} characters]", file=sys.stderr)


def cmd_add(args):
    data = _data()
    body = sys.stdin.read() if args.body == "-" else args.body
    session = capture.manual_session(args.cwd)
    sdir = store.staging_dir(data) / f"cli-{slugify(args.name)}"
    sdir.mkdir(parents=True, exist_ok=True)
    capture.write_session(sdir, session)
    meta = {"name": args.name, "type": args.type, "scope": args.scope, "description": args.description}
    atomic_write(sdir / f"{slugify(args.name)}.md", frontmatter.join(meta, body))
    capture.flush(data, sdir, final=True)
    print("saved")


def cmd_flush(args):
    data = _data()
    root = store.staging_dir(data)
    for sdir in sorted(root.iterdir()) if root.is_dir() else []:
        if sdir.is_dir() and any(sdir.glob("*.md")):
            capture.flush(data, sdir, final=False)
            print(f"flushed {sdir.name}")


def cmd_relocate(args):
    """Re-attribute existing memories recorded in throwaway folders."""
    from . import sessions, workdir

    data = _data()
    mdir = store.memories_dir(data)
    moved = 0
    for m in store.load_all(data):
        src = m["source"]
        if src.get("original_cwd") or not workdir.is_throwaway(src.get("cwd")):
            continue
        if args.only and not any(o in m["rel"] for o in args.only):
            continue
        transcript = src.get("transcript") or sessions.transcript_path(src.get("tool"), src.get("session_id"))
        ctx = capture.relocate({"cwd": src["cwd"], "host": src.get("host")}, transcript)
        if not ctx.get("original_cwd"):
            print(f"keep  {m['rel']}  (no project found)")
            continue
        print(f"move  {m['rel']}  {src['cwd']} -> {ctx['cwd']}")
        moved += 1
        if args.dry_run:
            continue
        meta, body = store.read(mdir / m["rel"])
        source = dict(meta.get("source") or {})
        for key in ("cwd", "git_root", "git_remote", "git_branch"):
            source.pop(key, None)
            if ctx.get(key):
                source[key] = ctx[key]
        source["original_cwd"] = ctx["original_cwd"]
        if transcript:
            source.setdefault("transcript", transcript)
        meta["source"] = source
        atomic_write(mdir / m["rel"], frontmatter.join(meta, body))
    if moved and not args.dry_run:
        with gitsync.Lock(data, timeout=30):
            gitsync.commit(data, f"relocate: {moved} memories from throwaway folders\n\nTool: relocate")
        gitsync.spawn_sync(data, push=True)
    print(f"{moved} to move" if args.dry_run else f"moved {moved}")


def cmd_lint(args):
    from . import lint

    data = _data()
    mdir = store.memories_dir(data)
    memories = store.load_all(data)
    names = {m["name"] for m in memories if m["name"]}
    picked = [
        m for m in memories if not args.only or any(k in (m["id"], m["name"]) or k in m["rel"] for k in args.only)
    ]
    flagged, kinds = 0, {}
    for m in picked:
        try:
            _, body = store.read(mdir / m["rel"])
        except OSError:
            continue
        issues = lint.check(m, body, names)
        if not issues:
            continue
        flagged += 1
        for kind, _ in issues:
            kinds[kind] = kinds.get(kind, 0) + 1
        if not args.summary:
            print(select.line(m))
            for _, message in issues:
                print(f"    - {message}")
    if not flagged:
        print(f"all {len(picked)} memories follow the format")
        return 0
    detail = ", ".join(f"{n} {lint.KINDS[k]}" for k, n in sorted(kinds.items(), key=lambda kv: -kv[1]))
    if not args.summary:
        print()
    print(f"{flagged} of {len(picked)} memories need tidying: {detail}")
    return 1


def cmd_ui(args):
    from . import demo, ui, ui_server

    if args.fetch_model:
        return ui.fetch_model()
    if args.demo:
        # in a new process, so every path the config module works out on import points into the demo
        demo.prepare()
        again = (
            ["ui", "--port", str(args.port)] + ["--no-open"] * args.no_open + ["--keywords-only"] * args.keywords_only
        )
        os.execv(sys.executable, [sys.executable, "-m", "agent_memory", *again])
    if os.environ.get(demo.ENV):
        print("Demo: made-up memories in a temporary repository; nothing you change is kept.", flush=True)
        atexit.register(shutil.rmtree, os.environ[demo.ENV], ignore_errors=True)
    ui_server.run(_data(), port=args.port, open_browser=not args.no_open, semantic=not args.keywords_only)


def cmd_sync(args):
    ok = gitsync.sync(_data(), push=not args.pull_only)
    if not args.quiet:
        print("synced" if ok else "sync failed; see .cache/agent-memory.log in the data repository")
    return 0 if ok else 1


def cmd_init(args):
    from .install import init_data

    init_data(Path(args.data_dir).expanduser())


def cmd_install(args):
    from .install import install

    install(dry_run=args.dry_run, claude=not args.no_claude, codex=not args.no_codex)


def cmd_uninstall(args):
    from .install import uninstall

    uninstall(dry_run=args.dry_run)


def cmd_import(args):
    from . import importers

    importers.run(args.source, _data(), dry_run=args.dry_run)


def cmd_doctor(args):
    from .install import doctor

    return doctor()


def cmd_hook(args):
    return hooks.main(args.event, args.tool)


def main(argv=None):
    p = argparse.ArgumentParser(prog="mem", description="Shared memory for Claude Code and Codex")
    sub = p.add_subparsers(dest="cmd", required=True)

    def scoped(sp):
        sp.add_argument("--cwd", help="evaluate from this folder instead of the current one")
        sp.add_argument("--type", choices=TYPES)
        g = sp.add_mutually_exclusive_group()
        g.add_argument("--global", dest="glob", action="store_true", help="global memories only")
        g.add_argument("--here", action="store_true", help="memories of this location only")
        sp.add_argument("--all", action="store_true", help="include memories from other locations")
        sp.add_argument("--limit", type=int, default=50)

    sp = sub.add_parser("list", help="list memories visible from here")
    scoped(sp)
    sp.set_defaults(fn=cmd_list)

    sp = sub.add_parser("search", help="full-text search")
    sp.add_argument("terms", nargs="+")
    scoped(sp)
    sp.set_defaults(fn=cmd_search)

    sp = sub.add_parser("show", help="print one memory")
    sp.add_argument("key", help="id, name or path")
    sp.set_defaults(fn=cmd_show)

    sp = sub.add_parser("index", help="print the index a session here would get")
    sp.add_argument("--cwd")
    sp.set_defaults(fn=cmd_index)

    sp = sub.add_parser("add", help="save a memory from the command line")
    sp.add_argument("--name", required=True)
    sp.add_argument("--type", choices=TYPES, required=True)
    sp.add_argument("--scope", choices=SCOPES, required=True)
    sp.add_argument("--description", required=True)
    sp.add_argument("--cwd")
    sp.add_argument("body", help="memory text, or - to read stdin")
    sp.set_defaults(fn=cmd_add)

    sp = sub.add_parser("flush", help="commit every staged memory now")
    sp.set_defaults(fn=cmd_flush)

    sp = sub.add_parser("relocate", help="attribute memories from throwaway folders to real projects")
    sp.add_argument("only", nargs="*", help="limit to memories whose path contains one of these")
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(fn=cmd_relocate)

    sp = sub.add_parser("lint", help="list memories that do not follow the body format in PROTOCOL.md")
    sp.add_argument("only", nargs="*", help="check only these ids, names or paths")
    sp.add_argument("--summary", action="store_true", help="print only the counts")
    sp.set_defaults(fn=cmd_lint)

    sp = sub.add_parser("ui", help="search, filter, read and edit memories in a local web page (needs numpy)")
    sp.add_argument("--port", type=int, default=8790)
    sp.add_argument("--no-open", action="store_true", help="print the link without opening a browser")
    sp.add_argument("--keywords-only", action="store_true", help="skip the embedding model")
    sp.add_argument(
        "--fetch-model", action="store_true", help="download the local embedding model (about 625 MB) and exit"
    )
    sp.add_argument(
        "--demo", action="store_true", help="open made-up memories in a temporary repository instead of yours"
    )
    sp.set_defaults(fn=cmd_ui)

    sp = sub.add_parser("sync", help="pull and push the data repository")
    sp.add_argument("--pull-only", action="store_true")
    sp.add_argument("--quiet", action="store_true")
    sp.set_defaults(fn=cmd_sync)

    sp = sub.add_parser("init", help="create or adopt a data repository")
    sp.add_argument("data_dir")
    sp.set_defaults(fn=cmd_init)

    sp = sub.add_parser("install", help="wire hooks into Claude Code and Codex")
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--no-claude", action="store_true")
    sp.add_argument("--no-codex", action="store_true")
    sp.set_defaults(fn=cmd_install)

    sp = sub.add_parser("uninstall", help="remove everything install added")
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(fn=cmd_uninstall)

    sp = sub.add_parser("import", help="copy native memories into the data repository")
    sp.add_argument("source", choices=["claude", "codex"])
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(fn=cmd_import)

    sp = sub.add_parser("doctor", help="check the installation")
    sp.set_defaults(fn=cmd_doctor)

    sp = sub.add_parser("hook", help=argparse.SUPPRESS)
    sp.add_argument("event", choices=["session-start", "stop", "session-end"])
    sp.add_argument("--tool", required=True, choices=["claude-code", "codex"])
    sp.set_defaults(fn=cmd_hook)

    args = p.parse_args(argv)
    return args.fn(args) or 0
