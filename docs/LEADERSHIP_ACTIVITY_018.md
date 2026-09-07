# Leadership activity — 0.18.0

The sticky header links to **Leadership activity**, showing unread completed actions and open approval requests across controlled businesses. Progress polling refreshes these counts while time advances. Routine actions introduce no new pauses; existing approvals and financial guardrails still apply.

Management overview now starts with a paginated history filtered by leader, business, and status. Entries show date, employee name, role at the time where recorded, business, action, result, immediate cash paid, and commitment or proposal amount. Requests show deadlines, recommendations, risks, and links to approval controls. The directory links to each leader's actions; each business shows its latest three completed actions.

Actual saved authority records supply the history, including stock purchases and project acceptance. Automatic jobs using the older automatic-job policy now generate audit entries without changing that path's budget enforcement. Available leaders are named; actions without an available leader are labeled Business automation. New records snapshot names/roles and capture real command results. Historical results or director identities are never invented.

Player-approved requests record execution results and immediate cash paid, labeled Resolved by Player. They do not become autonomous actions or incur duplicate authority charges. Pending/deferred proposals have no recorded payment. Commitments can include annualized base pay or future materials; they are not an extra cash charge. Internal parent authority charges do not duplicate action counts.

Mark current actions as read saves a monotonic audit cursor across businesses, including when viewing a filtered history. It marks only actions present when the screen was rendered, survives reload, and never approves or dismisses a pending request. Opening the page alone is read-only.

Compatibility and limits:

- Existing audit history appears unread on first use. Old requests lacking an actor show No leader recorded. Old roles and outcomes remain unspecified unless saved.
- History includes currently controlled businesses and their closed operations, excluding sellers. Former employees remain named; employee links are available only for current accessible records.
- Automatic receipts, payroll accrual, and passive operational output are not labeled director decisions. Missing historical actions are not reconstructed.
- No schema migration, financial transfer, or policy change is required. Stable IDs and existing authority enforcement remain intact.

Validation performed:

- Nine dedicated tests cover real purchases and cost display, stable actor names, requests versus actions, review cursor/save-load, legacy data, filters/pagination, parent-charge deduplication, HTTP pages/live notifications, daily stock purchases, and automatic jobs with/without directors.
- Leadership/authority/navigation regression: 37 passed. Final dedicated/project/authority regression: 43 passed.
- Browser using an isolated campaign copy: followed the indicator, filtered completed actions, and marked actions read while leaving an approval open. After eight simulated days in the copy, Jamie Clarke's April 20 engineering project acceptance appeared with the actual fee/workload and a renewed unread count.
- Final full regression: 341 passed in 167.33 seconds, with two existing dependency deprecation warnings. Source-only installation preserves the campaign and verifies per-file hashes and ten installed page views.
