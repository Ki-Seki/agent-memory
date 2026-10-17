<p align="center">
  <img src="https://raw.githubusercontent.com/Ki-Seki/agent-memory/main/docs/logo.svg" width="64" height="64" alt="">
</p>

<h1 align="center">agent-memory</h1>

<p align="center">
  <b>One memory for Claude Code and Codex.</b><br>
  What your agents learn, kept as plain Markdown in a git repository you own.
</p>

<p align="center">
  <a href="https://ki-seki.github.io/agent-memory/demo/"><b>Live demo</b></a> ·
  <a href="https://ki-seki.github.io/agent-memory/">Website</a> ·
  <a href="https://ki-seki.github.io/agent-memory/docs.html">Docs</a>
</p>

<p align="center">
  <a href="https://pypi.org/project/agent-memory-git/"><img src="https://img.shields.io/pypi/v/agent-memory-git?color=5b5bd6" alt="PyPI"></a>
  <a href="https://pypi.org/project/agent-memory-git/"><img src="https://img.shields.io/pypi/pyversions/agent-memory-git?color=5b5bd6" alt="Python"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-5b5bd6" alt="MIT license"></a>
</p>

<a href="https://ki-seki.github.io/agent-memory/demo/">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Ki-Seki/agent-memory/main/site/assets/shots/memories-dark.png">
  <img alt="mem ui, open in the live demo: a list of memories on the left, one open on the right with where it came from" src="https://raw.githubusercontent.com/Ki-Seki/agent-memory/main/site/assets/shots/memories-light.png">
</picture>
</a>

## Why agent-memory

- **Tell one agent, both remember.** A preference you give Codex is there the next time Claude
  Code starts, and the other way round, on every machine that pulls.
- **The right memories in each session.** Everything global, plus what was learned in this folder
  or repository, and nothing from your other projects.
- **Memory in git.** One Markdown file per memory in a git repository you own, with where it came
  from recorded by the hooks. Every change is a commit you can review or revert; add a private
  remote to sync machines, or keep it all on one. Here is [an example](https://github.com/Ki-Seki/agent-memory-data-demo).
  [Profiles](https://ki-seki.github.io/agent-memory/docs.html#profiles) keep separate sets of
  memories in repositories of their own, and a switch reaches running sessions too.
- **Nothing to run.** Two hooks and git. No service, no account; search by meaning runs on your CPU.
- **A page to keep it tidy.** `mem ui` searches by words and by meaning, edits with undo, and shows
  what changed week by week.

## Quick start

See it first, with nothing installed:

```bash
uvx --from "agent-memory-git[ui]" mem ui --demo
```

Then set it up (Python 3.11+, git and [uv](https://docs.astral.sh/uv/)):

```bash
uv tool install "agent-memory-git[ui]"
mem init ~/repos/agent-memory-data   # your data repository
mem install --dry-run                # every change, as a diff
mem install
```

Codex asks you to trust new hooks once: open `/hooks` in Codex and enable the three agent-memory
hooks. The [docs](https://ki-seki.github.io/agent-memory/docs.html#install) cover importing existing
memories, every file `mem install` changes, upgrading and uninstalling.

## How it works

![mem install wires hooks into Claude Code and Codex; at session start they load an index from the private data repository, and at the end of each turn they commit and push new memories back](https://raw.githubusercontent.com/Ki-Seki/agent-memory/main/docs/how-it-works.svg)

At session start a hook gives the agent an index of the memories that apply where it runs. The
agent saves what is worth keeping as Markdown files, following
[PROTOCOL.md](src/agent_memory/PROTOCOL.md), and at the end of each turn a hook records where each
came from, commits and pushes. The [docs](https://ki-seki.github.io/agent-memory/docs.html) explain
the file format, where memories load, the commands and the configuration.

## Contributing

```bash
uv sync --all-extras && uv run pytest
```

The `mem ui` page is plain HTML, CSS and JavaScript with no build step, and
`uv run scripts/site.py serve` runs the website and its live demo locally. More in the
[docs](https://ki-seki.github.io/agent-memory/docs.html#development).

## License

[MIT](LICENSE)
