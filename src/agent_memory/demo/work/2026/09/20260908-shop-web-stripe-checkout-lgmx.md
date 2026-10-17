---
id: 20260908-shop-web-stripe-checkout-lgmx
name: shop-web-stripe-checkout
type: project
scope: here
description: shop-web checkout moved to the Stripe Payment Element in September; the old Charges API code path is dead
created: 2026-09-08T14:10:00+08:00
source:
  tool: claude-code
  session_id: 1012f037-b64c-4422-8c38-fb2918f135d2
  session_name: shop-web-checkout
  host: alex-laptop
  cwd: /Users/alex/code/shop-web
  git_root: /Users/alex/code/shop-web
  git_remote: git.example.com/shop-web
  git_branch: main
---
Checkout in shop-web now uses the Stripe Payment Element (`src/checkout/PaymentForm.tsx`). The old Charges API path in `src/legacy/charge.ts` is no longer called and is kept only until the v3 cleanup.

**Why:** Charges API is deprecated, and 3-D Secure needed the Payment Element.

**How to apply:** do not fix bugs in `src/legacy/`; change the Payment Element flow instead. See [[shop-web-deploys]] before shipping.
