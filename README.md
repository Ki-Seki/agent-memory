# agent-memory

One memory system for Claude Code and Codex. Every memory is a Markdown file in a separate git
repository (the data repository); this repository holds only the code that reads and writes it.

## How it works

- **One file per memory.** Frontmatter carries `type` (user / feedback / project / reference),
  `scope` (global / here), a one-line `description`, and provenance under `source`: tool, session
  id and name, model, host, folder, git root, remote, branch and commit. Files live in
  `memories/YYYY/MM/<id>.md`; the folders exist only to keep listings short.
- **Session start.** A SessionStart hook works out where the session runs (folder, host, git
  identity), picks every `global` memory plus the `here` memories recorded at the same place,
  and injects a compact index (under 10,000 characters, the Claude Code hook limit).
- **Writing.** The agent writes new memories into a per-session staging folder and edits existing
  files in place. At the end of each turn a Stop hook stamps ids and provenance, moves staged
  files into `memories/`, commits, and pushes in the background. The agent never writes
  provenance itself.
- **Rules.** [`PROTOCOL.md`](PROTOCOL.md) tells the agent what to save and how. Claude Code
  imports it from `~/.claude/CLAUDE.md`; Codex gets a copy in `~/.codex/AGENTS.md`.

Sessions in throwaway folders (Claude Code scratch workspaces, Codex per-thread folders under
`~/Documents/Codex/<date>/`) get their `here` memories filed under the project folder the
transcript shows them working in most, with the original folder kept as `source.original_cwd`.
`mem relocate` applies the same inference to existing memories. Patterns can be overridden with
`throwaway_patterns` in `~/.config/agent-memory/config.json`.

A `here` memory matches a session when they share the folder (100), the git checkout (90), the
remote (80, other clones and worktrees), or when one folder contains the other (70 / 60). Home
and its direct children such as `~/repos` are too broad to match through containment.

## Setup

Requires Python 3.11+ and git.

```bash
bin/mem init ~/repos/agent-memory-data     # create the data repository and ~/.config/agent-memory
bin/mem import claude --dry-run            # preview, then run without --dry-run
bin/mem import codex --dry-run
bin/mem install --dry-run                  # shows every change as a diff
bin/mem install
```

`install` edits, and records in `~/.config/agent-memory/install-state.json`:

| File | Change |
|---|---|
| `~/.claude/settings.json` | SessionStart / Stop / SessionEnd hooks, `autoMemoryEnabled: false`, read/edit permission on the data repository, `mem search/list/show` allowed |
| `~/.claude/CLAUDE.md` | a marked block importing `PROTOCOL.md` |
| `~/.codex/hooks.json` | the same three hooks |
| `~/.codex/config.toml` | `memories.generate_memories = false`, `memories.use_memories = false`, data repository added to `sandbox_workspace_write.writable_roots` |
| `~/.codex/AGENTS.md` | a marked block with the protocol |
| `~/.local/bin/mem` | symlink to `bin/mem` |

Codex asks you to trust new hooks once: open `/hooks` in Codex and enable the three
agent-memory hooks.

`mem uninstall` reverts exactly those edits (other changes the tools made in the meantime are
kept) and turns native memory back on. The data repository is never touched by uninstall.

## Commands

```
mem index [--cwd DIR]           what a session started here would see
mem list [--global|--here|--all] [--type T]
mem search WORDS... [--all]     full-text search; --all includes other locations
mem show ID|NAME|PATH
mem add --name N --type T --scope S --description D BODY|-
mem flush                       commit anything left in staging
mem relocate [PATH...] [--dry-run]  re-file memories recorded in throwaway folders
mem sync [--pull-only]          pull --rebase and push the data repository
mem doctor                      check the installation
```

## Notes

- Hooks never fail the host session; errors go to `<data>/.cache/agent-memory.log`.
- Git operations are serialized with a lock file, so parallel sessions are safe on one machine.
  Across machines, unique file names keep merge conflicts rare; a failed rebase is aborted and
  logged for you to resolve.
- Session names come from Claude Code's `custom-title` transcript entries and Codex's thread
  database, when available.
