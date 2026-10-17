---
id: 20260816-blog-publishing-k3qm
name: blog-publishing
type: project
scope: here
description: "blog: posts are Markdown in content/posts and a push to main publishes them; drafts stay in content/drafts"
created: 2026-08-16T20:40:00+08:00
source:
  tool: codex
  session_id: 58653a77-5fdc-4a8c-91e3-2a91b3a7875d
  session_name: blog-rss-feed
  host: alex-laptop
  cwd: /Users/alex/code/blog
  git_root: /Users/alex/code/blog
  git_remote: git.example.com/blog
  git_branch: main
---
The blog is a static site: posts are Markdown files in `content/posts`, and every push to `main` builds and publishes it. Unfinished posts go in `content/drafts`, which is never built.

**Why:** there is no review step, so anything on `main` is live within a minute.

**How to apply:** start new posts in `content/drafts`, and move one to `content/posts` only when Alex says to publish it.
