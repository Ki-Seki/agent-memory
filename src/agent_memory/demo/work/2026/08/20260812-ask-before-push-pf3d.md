---
id: 20260812-ask-before-push-pf3d
name: ask-before-push
type: feedback
scope: global
description: Ask before every git push, and keep each commit to one change
created: 2026-08-12T15:40:00+08:00
source:
  tool: claude-code
  session_id: f28c105d-1fb1-4c23-90c1-92cfd3ac94af
  session_name: shop-web-checkout
  host: alex-laptop
  cwd: /Users/alex/code/shop-web
  git_root: /Users/alex/code/shop-web
  git_remote: git.example.com/shop-web
  git_branch: main
---
Ask Alex before every `git push`, even when an earlier push in the same session was approved. Keep each commit to one change.

**Why:** a force-push once overwrote a teammate's commit on a shared branch.

**How to apply:** commit locally as you go, then list the commits and ask before pushing. Split unrelated edits into separate commits.
