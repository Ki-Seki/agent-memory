---
id: 20260922-design-tokens-source-uvw7
name: design-tokens-source
type: reference
scope: global
description: Design tokens (colours, spacing, type) live in git.example.com/design-tokens and sync into shop-web weekly
created: 2026-09-22T13:15:00+08:00
source:
  tool: claude-code
  session_id: 119a72d1-74c9-4f6a-8c01-1cdd9474031b
  session_name: shop-web-theme
  host: alex-laptop
  cwd: /Users/alex/code/shop-web
  git_root: /Users/alex/code/shop-web
  git_remote: git.example.com/shop-web
  git_branch: main
---
Colours, spacing and type scales come from `git.example.com/design-tokens`. A weekly bot PR copies them into `shop-web/src/theme/tokens.ts`.

**How to apply:** change tokens in design-tokens, not in shop-web; local edits are overwritten by the next sync.
