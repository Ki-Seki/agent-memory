---
id: 20260915-etl-parquet-partitioning-seh2
name: etl-parquet-partitioning
type: project
scope: here
description: etl-jobs 的 Parquet 按日期分区而不是按客户；改分区前要先迁移历史数据
created: 2026-09-15T19:20:00+08:00
source:
  tool: claude-code
  session_id: 26e87555-5790-482e-81d3-fcff2a3af4d4
  session_name: etl-backfill
  host: alex-laptop
  cwd: /Users/alex/code/etl-jobs
  git_root: /Users/alex/code/etl-jobs
  git_remote: git.example.com/etl-jobs
  git_branch: main
---
etl-jobs 写出的 Parquet 按 `dt=YYYY-MM-DD` 分区，不按客户分区。下游报表都假设这个布局。

**Why:** 按客户分区会产生上万个小文件，查询反而变慢。

**How to apply:** 想改分区方式，先写迁移脚本处理历史数据，再改写入逻辑。
