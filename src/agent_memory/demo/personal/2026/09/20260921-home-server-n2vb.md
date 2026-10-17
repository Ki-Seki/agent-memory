---
id: 20260921-home-server-n2vb
name: home-server
type: reference
scope: global
description: "Home server nas.home.arpa: Jellyfin on port 8096, nightly backups of /srv to the USB drive at 03:00"
created: 2026-09-21T16:30:00+08:00
source:
  tool: codex
  session_id: de0fd804-e67d-4793-9580-dd285f8f7eda
  session_name: homelab-backups
  host: alex-laptop
  cwd: /Users/alex/code/homelab
  git_root: /Users/alex/code/homelab
  git_remote: git.example.com/homelab
  git_branch: main
---
The home server is `nas.home.arpa` on the home network. Jellyfin runs on port 8096, configured from `jellyfin/` in the homelab repository. `/srv` is backed up every night at 03:00 to the USB drive mounted at `/mnt/backup`.
