---
id: 20260902-report-eta-is2j
name: report-eta
type: feedback
scope: global
description: 长任务开跑时要报预计完成时间，用上海时间
created: 2026-09-02T21:30:00+08:00
source:
  tool: claude-code
  session_id: 4ef8aa38-9227-4658-9e27-a1c08a6a63ec
  session_name: etl-backfill
  host: alex-laptop
  cwd: /Users/alex/code/etl-jobs
  git_root: /Users/alex/code/etl-jobs
  git_remote: git.example.com/etl-jobs
  git_branch: main
---
启动任何超过几分钟的任务（回填、训练、批量导出）时，先说还要多久、预计上海时间几点完成。

**Why:** Alex 需要据此安排什么时候回来看结果。

**How to apply:** 开跑时报一次，进度明显偏离时再更新一次。
