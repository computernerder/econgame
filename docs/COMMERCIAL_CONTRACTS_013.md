# Contracts and purchasing — 0.13.0

Open **Contracts & purchasing** beneath the cash header. This increment extends the existing service queues, authority contracts, property work and double-entry accounts. One business or a personal property portfolio can purchase outside expertise without creating headquarters.

## Implemented behavior

- New **Covenant Works** industrial listings disclose a buyer-specific transfer restriction, a closing fee and a 90-day roof obligation before any review is ordered. Ordinary listings retain their purchase rules. Buying a property still does not buy its tenants.
- Transaction review consumes legal capacity and produces a record of the existing disclosure and a repair estimate with uncertainty. A subsequent consent application can fail. Successful negotiation records the original and agreed closing fee, and clearance applies only to that buyer. Large industrial consents require an outside specialist; a mixed delivery label does not bypass the requirement. Refusals cannot be rerolled by commissioning the same application again.
- A cleared purchase capitalizes actual closing costs and creates the disclosed roof covenant. Cash forecasts reserve a replacement budget until replacement is booked or actual condition satisfies the obligation. Small preventive jobs cannot hide the commitment. Completion checks actual condition, warns near the deadline and posts the agreed missed-deadline liability once. Repair resources, disruption, workmanship and callbacks use the existing property-work simulation.
- Purchasing staff or outside advisers can obtain supplier responses for a chosen service department. Work takes time; counterparties can refuse. Offers have different block sizes, rates and shared daily capacity, and expire after 14 days.
- Buying an agreement prepays the whole block. Matching outside tasks automatically reserve its minutes when the block can fund the entire task. Simultaneous tasks share the provider's daily capacity in priority/deadline order. Overloaded tasks still raise overdue alerts even when they receive zero work that day.
- Unassigned credit expires after 60 days and becomes an expense. Previously assigned work remains deliverable. Cancelling unfinished work returns unused minutes to an unexpired agreement, or expenses them after expiry; it cannot turn nonrefundable credit into cash.
- The new screen shows disclosures, completed legal work, quoted rates, actual expenses, future concessions, available credit, task reserves, expired losses and inherited obligations. The management selector retains this screen when changing accounts.

## Financial and authority treatment

Purchasing a block debits `asset:service_credit` and credits cash. Reserving work transfers credit to `asset:prepaid_services`; actual delivery becomes `expense:outside_services`. Expired credit becomes `expense:unused_service_credit`. Validation reconciles paid cost to available credit, task reserves, delivered expense and expired loss, and reconciles credit with each buyer's ledger.

Supplier purchases use the full upfront price in delegated purchasing checks, including cumulative period limits and minimum reserves. An offer for one entity cannot be purchased or consumed by another. No recurring commitment or automatic block-renewal planner is introduced. Existing internal labor allocation and consolidated charge eliminations remain in force.

Legal fee concessions are future purchase cost reductions, not cash income. A missed covenant creates an actual payable that enters the existing distress system. The initial purchaser retains its covenant responsibility even if it later transfers the property; this release does not model automatic novation or obligation renegotiation. A booked replacement funds the known work; any failed workmanship is reassessed when work completes.

## Persistence and validation

The migration creates a uniquely named `before-commercial-contracts` SQLite recovery backup, retains previous accounts, existing employment records and campaign date, and advances the systems compatibility marker to 4. Older engines reject the new marker. Restart the launcher after installation; the installation itself does not replace or advance the campaign.

See [executed validation](VALIDATION.md) for the final test count and campaign-copy browser checks. Tests cover buyer-specific consent, factual disclosures, refusals, specialist escalation, repair commitments, breach liabilities, shared supplier capacity, priority, expiry, cancellation, authority, replay, migration and read-only pages.

## Limits and next increments

This is a bounded service-procurement and industrial-consent model. Blocks fund whole outside-only tasks; partial block funding, inventory supplier agreements, recurring procurement plans, supplier insolvency and a general contract editor remain open. The tender's own cost must be justified by expected workload; small one-off jobs can use ordinary outside service reservations.

Legal review currently analyzes published obligations; broader hidden-obligation discovery, litigation stages, transferable consents and richer acquisition templates remain later work. Specialist service industries such as cleaning, landscaping, security, parking and hotels, and land assembly, feasibility, approvals, phased district development and preleasing remain explicit future increments. This release does not declare the entire original design complete.
