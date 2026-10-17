---
id: 20260820-tests-before-done-odzd
name: tests-before-done
type: feedback
scope: global
description: Run the tests before saying a change works, and quote the failing output when they fail
created: 2026-08-20T09:05:00+08:00
source:
  tool: codex
  session_id: 8e81973e-0bec-47b0-b898-d190f9ebdacc
  session_name: etl-nightly-export
  host: alex-laptop
  cwd: /Users/alex/code/etl-jobs
  git_root: /Users/alex/code/etl-jobs
  git_remote: git.example.com/etl-jobs
  git_branch: main
---
Before saying a change works, run the project's tests (`pytest -q` in etl-jobs, `pnpm test` in shop-web).

**Why:** twice a fix was reported as done while the suite was red.

**How to apply:** paste the summary line; if anything fails, show the failing output instead of paraphrasing it.
