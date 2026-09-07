# Blocker shortcuts — 0.19.1

When a long skip stops for owner approval, its status message now includes named links to the actual pending approval cards. Following a link scrolls to and highlights the card. The advance-time dialog also shows those links before a long skip begins. Up to three requests appear directly; larger queues include a link to the whole inbox. Deferred or resolved requests no longer supply stale anchors.

Other important-event and exception stops offer recovery navigation beside their explanation. Refused action previews and commands return recovery shortcuts, displayed with the error on the page or in the review dialog. Common funding, staffing, scheduling, authority, repair, lease, legal and service-capacity requirements lead to the related controls. Known owned business, property, employee and approval identifiers preserve the relevant context. Stale-screen errors offer refresh; a running-time error can reveal the existing pause control. The unpaid holding-cost warning also links to funding and obligations.

These are read-only navigation suggestions. Existing simulation rules, confirmation dialogs, authority checks, dated obligations and daily-step behavior are unchanged. Following a link never grants approval or commits spending. Normal completion and user-cancelled skips show no blocker shortcuts. Progress is still session state; restarting the game does not recreate an old skip banner, but pending approvals remain available through the advance dialog and inbox.

Known limits: category routing for common action errors uses their existing explanation text. Unrecognized errors offer the inbox and activity instead of guessing an exact remedy. Some recovery screens contain multiple controls; only management approvals and explicitly identified owned records get an exact record link. The links do not promise that financing or another remedy will succeed. Optional disabled controls with explanatory text elsewhere remain candidates for further contextual shortcuts.

Validation:

- Eight dedicated regression tests cover the actual zero-day approval stop and inbox anchor, preflight links, deferred-request cleanup, real rejected preview/command purchases with unchanged state, request context, untrusted IDs, employee identity, requirement categories, ordinary/cancelled progress, event/error fallbacks and bounded multi-request display.
- Full regression: 364 passed in 177.24 seconds, with two existing dependency deprecation warnings.
- Targeted inbox and recovery regression: 23 passed. A final targeted rerun verifies the direct business-capital anchor after browser feedback.
- Browser QA used a disposable copy of the campaign: opened advance-time controls, attempted a month skip, followed its named approval link to the highlighted card, and submitted an unaffordable stock purchase to verify funding shortcuts. Cash and simulated date remained unchanged.

Future decision-producing workflows should supply explicit destinations alongside their refusal reasons; retain the generic fallback for older rules.
