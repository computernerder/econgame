# Service projects and tenant requests — 0.12.0

This increment extends the 0.11 operating foundation. Existing departments, reports, basic hiring, property work, ownership scales and financial records remain available. A small company can purchase every new service outside the organization; headquarters is optional.

## Implemented behavior

| Workflow | Simulation and result |
| --- | --- |
| Role recruiting | HR spends 12 provider hours sourcing ordinary applicants for a specified industry role. Candidates retain their skills, qualifications and pay requirements. Recruiting does not hire them or guarantee elite abilities. |
| Candidate assessment | Four provider hours produce an uncertain skill range and a record of actual credentials. Quality affects uncertainty. True ability is not rewritten and no job offer is made. |
| Employee onboarding | Eight provider hours plus two paid participant hours, reserved at most one per scheduled employee day. Leave and missing capacity delay participation; completion requires both sides. The work affects trust and onboarding stress. A departed employee produces an accurate unsuccessful outcome, with incurred costs retained. |
| Succession review | Sixteen provider hours assess existing employees for a target role, including credential gaps, notice and uncertain readiness. A shortlist names stable employee identities. Promotion remains a separate vacancy/pay/credential decision; promotions now recheck target licenses. |
| Checkout deployment | Twenty-four provider hours deploy a system that improves existing staffed checkout throughput. No cashier time means no checkout output. Condition wears on operating weekdays, reducing the effect, and eventually the system ceases to help. |
| Inventory integration | Twenty-four provider hours enable two-day order targets based on recent observed demand, instead of the legacy five-day demand target. Orders still require real cash and purchasing authority. Smaller batches reduce tied-up inventory and expiry exposure without changing physical shelf life or creating stock. |
| System support | Eight provider hours restore installed condition. Managers with IT service renewal enabled request this specific project when condition reaches 60 or below, subject to existing availability, cooldown, scope, budget and reserve checks. |
| Cancellation | Unfinished service work can be cancelled. Delivered work remains an expense, unused outside prepayments return to cash, and no completed work product is granted. Remaining internal commitments are released, not refunded as fictional cash. |
| Tenant maintenance requests | Occupied external leases report an existing property system below 35 condition. Requests preserve observed/current condition and deadlines; severe conditions get a shorter deadline. Booking work does not resolve them. Actual recovery to serviceable condition resolves the request. Unresolved overdue problems reduce renewal ceilings by 10% and surface a skip interruption. |
| Delegated tenant response | Property-operation managers can propose qualified repair work for requests. Existing authority checks include the actual owning entity, geography, cash and future labor. The player can also book responses through Property workbench. |

Projects use the existing internal/outside/mixed queue, actual provider time, wages and cost allocation. Outside effort reserves cash at $1.50 per provider minute. Internal queues compete for finite capacity; allocations remain eliminated from consolidated results. Onboarding also removes participant minutes from their operating shift. New screens show specific project names, unused prepayments, succession estimates, participation, deployed condition and repair requests.

## Persistence and validation

Campaign systems version 3 marks these saved projects. Opening a supported prior campaign creates a `before-service-projects` SQLite backup, preserves existing people/balances/date and updates the subsystem. Older 0.11 code rejects version 3 rather than silently dropping its workflows; restore a matching backup if rolling back. Installation backs up source and never replaces live campaign saves.

The full suite passed 243 tests before two additional delegation/skip tests. The final targeted result and browser/installed verification are recorded in VALIDATION.md. Seeded daily replay, save/load, journal reconciliation, queue overload, cancellation, false-success avoidance, cash limits and repair outcomes are covered.

## Remaining scope and next increment

These are specific service workflows, not exhaustive HR or IT simulations. Succession planning does not create automatic executive appointments, a retirement estate system or guaranteed retention. IT uses a manageable deployed-condition model, not hardware networks or cybersecurity incidents. Tenant requests cover the worst currently reported system per external lease; they are fictional operating rules, not jurisdiction-specific tenancy law.

Next: deeper legal transaction obligations/reviews and service purchasing contracts, then specialist property-service industries and district development. Land assembly, feasibility, approvals, phased construction, preleasing and district improvements remain explicit later work. Long-portfolio balance, large-workforce performance and clean-PC installer qualification remain unverified.
