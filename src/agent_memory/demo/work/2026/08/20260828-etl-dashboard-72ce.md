---
id: 20260828-etl-dashboard-72ce
name: etl-dashboard
type: reference
scope: global
description: "etl-jobs run history and alerts: the Grafana dashboard at grafana.example.com/d/etl-runs"
created: 2026-08-28T10:00:00+08:00
source:
  tool: codex
  session_id: ca02135e-92b1-43f2-8ede-0d7ac3baea9e
  session_name: etl-nightly-export
  host: alex-laptop
  cwd: /Users/alex/code/etl-jobs
  git_root: /Users/alex/code/etl-jobs
  git_remote: git.example.com/etl-jobs
  git_branch: main
---
Run history, durations and failure alerts for every etl-jobs job are on the Grafana dashboard `grafana.example.com/d/etl-runs`. The `orders_export` panel shows how close each night came to the 06:00 deadline ([[etl-orders-export-deadline]]).
