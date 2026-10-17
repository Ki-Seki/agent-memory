---
id: 20260827-etl-orders-export-deadline-pft7
name: etl-orders-export-deadline
type: project
scope: here
description: "etl-jobs: the nightly orders export must finish before 06:00 because finance reads it at 06:30"
created: 2026-08-27T08:30:00+08:00
source:
  tool: codex
  session_id: 72e6cc3a-babc-4d20-97ee-05cde00902c7
  session_name: etl-nightly-export
  host: alex-laptop
  cwd: /Users/alex/code/etl-jobs
  git_root: /Users/alex/code/etl-jobs
  git_remote: git.example.com/etl-jobs
  git_branch: main
---
The `orders_export` job in etl-jobs runs at 01:00 and must finish before 06:00 (Shanghai time); finance pulls the file at 06:30.

**Why:** the daily revenue report is built from it; a late file delays that report for everyone.

**How to apply:** do not add heavy steps to `orders_export`; anything slow goes in a separate job after 06:30.
