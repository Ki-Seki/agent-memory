---
id: 20261012-payments-runbook-4syw
name: payments-runbook
type: reference
scope: global
description: "On-call runbook for payment failures: docs.example.com/runbooks/payments"
created: 2026-10-12T09:40:00+08:00
source:
  tool: codex
  session_id: 5affb229-7631-4992-b0ce-583505c6af07
  session_name: shop-web-oncall
  host: alex-laptop
  cwd: /Users/alex/code/shop-web
  git_root: /Users/alex/code/shop-web
  git_remote: git.example.com/shop-web
  git_branch: main
---
When checkout payments fail, follow `docs.example.com/runbooks/payments`: check the Stripe status page, then the webhook queue, then recent shop-web deploys. Background: [[shop-web-stripe-checkout]].
