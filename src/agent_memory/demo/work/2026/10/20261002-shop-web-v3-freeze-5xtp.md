---
id: 20261002-shop-web-v3-freeze-5xtp
name: shop-web-v3-freeze
type: project
scope: here
description: "shop-web v3 feature freeze on 2026-11-01: no schema migrations after that date"
created: 2026-10-02T16:45:00+08:00
source:
  tool: claude-code
  session_id: c7a2ea20-b2f1-4c94-ae05-319acb5c7427
  session_name: shop-web-v3-plan
  host: alex-laptop
  cwd: /Users/alex/code/shop-web
  git_root: /Users/alex/code/shop-web
  git_remote: git.example.com/shop-web
  git_branch: main
---
Feature freeze for shop-web v3 is 2026-11-01. After that only bug fixes land; no database schema migrations until the v3 release.

**Why:** the data team snapshots the schema for the Q4 reporting work.

**How to apply:** if a change needs a migration, flag it before the freeze. Release flow: [[shop-web-deploys]].
