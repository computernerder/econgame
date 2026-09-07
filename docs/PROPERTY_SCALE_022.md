# Property scale and staffed support — 0.22.0

The original handoff remains the long-term design. This increment extends existing ownership, payroll, leases, service queues and repair accounting.

## Play at your current scale

- A single property can use outside contractors or owner-performed basic interior/exterior repairs. Owner work consumes four hours per simulated day and leaves two discretionary actions per day. Reading, time advancement, required management/leave approvals and funding/recovery remain available. Outsource the remainder to regain decision capacity. New uses of the old self-renovation command enter this same basic-work workflow; already funded legacy renovations finish normally.
- An owned trade company or home office can employ electricians, plumbers and HVAC technicians. Valid electrical, plumbing and HVAC licenses are mandatory for their respective systems. Maintenance skill alone does not replace a license. Existing staff receive no invented licenses. New qualified candidates, recruiting, and 30-day credential courses provide a route to coverage; trade courses require a prior trade qualification.
- Repair delivery consumes each eligible employee's remaining productive minutes, with leave, schedules, training and existing allocations reflected in the pool. A selected licensed employee cannot borrow unrelated staff hours. Internal work allocates actual payroll/benefit/tax cost; it displaces outside work. Travel consumes capacity. Qualified crews may finish sooner than an outside contractor's four-hour daily reservation, but idle or absent crews provide no speed advantage. General repair jobs can still wait for staff and be outsourced for recovery.
- Trade specialists' remaining time contributes to their trade/construction business's external projects. Creating an empty company or role provides no permanent discount or capacity.

## Agent and HR services

Hire a licensed **Real estate agent** into a home office or property-management business. Configure its matching department in **Home office services**, then request **Use an in-house real estate agent** for a specific buyer/seller and property. Sixteen qualified service hours prepare a single closing. Completion reduces brokerage by 70% for that transaction within 90 days; legal/consent fees remain. On a normal purchase the brokerage component changes from 2% to 0.6%; on a sale, 3% to 0.9%. Allocated staff costs remain real expenses. The digest records actual fee reductions only when used. Another account or transaction cannot reuse the certificate.

HR project searches, candidate assessments, onboarding and succession continue to use finite service queues. Sourced applicants' skills are initially unobserved; assessment records an uncertain estimate, not a perfect employee or an accepted offer. The hiring page links directly to these services and shows recorded project sourcing, hiring, assessment, queue and delivery-cost statistics.

Banked qualified HR work also improves ordinary recruitment: 240 minutes reduce a campaign fee by $150, produce five ordinary applicants instead of three and shorten its lead time by two days. Screening consumes 120 banked HR minutes when available, costs $25 instead of $100 and narrows the recorded skill band from ten to five points. Credits are consumed, expire under the existing specialist rules, and cannot be spent twice. Hiring qualifications and pay acceptance still apply. Shared HR must deliver or assign work to the receiving business; simply employing someone elsewhere does not give every company free credits.

## Land and buildings

Each district gains a starter lot and a larger development lot. Lot identities do not consume prior transaction IDs or economic random draws. Land earns no building rent and incurs holding costs. Compare designs and construction budgets on the lot page before purchase.

Ten designs cover residential homes, boutique/general-retail storefronts, grocery, restaurants, offices, factories, trade workshops, warehouses/storage, fuel stations and dealership showrooms. Each supports starter, established and large sizes when the lot has room for the building and access/setbacks. Sizes change floor area, construction capital, duration, rent potential and operating upkeep. A boutique or factory building restricts owned occupancy to compatible industries; it does not buy an operating business, machines, inventory or tenants. Completed use conversions remove the original specialization restriction.

Construction reserves the full budget, approvals and 10% contingency at authorization. Daily completed work moves reserve into historical property cost. Seeded site costs consume a bounded share of contingency; unused funds return at completion. Holding costs continue outside this reserve. New systems begin at age zero. Finished value follows comparable design values, market cycle and workmanship, not a guaranteed markup over spending. Development can cost more than its estimated completed value. Lease or occupy the vacant finished building separately.

## Interface

Property detail pages put eight building systems, condition, age, license requirements and active work above the financial purchase panel. Empty lots show suitable designs. The workbench shows repair needs and underway construction before optional forms, with detailed comparisons collapsed and shortcuts to repairs, outsourcing, agent help and construction. The owner repair-time limit is visible across the game.

## Persistence and limits

Opening an older compatible save creates a `before-property-scale-*.sqlite3` backup and adds lots once. Existing property, person and employment identities, licenses, financial history and custom handoff notes are preserved. New reserves reconcile to the journal and save/load/daily-step behavior uses the same daily simulation.

Ground-up construction currently uses a funded outside delivery schedule; assigning owned construction crews to new builds is the next development increment. Permits and site costs are high-level fictional abstractions. Land assembly, rezoning disputes, staged finance draws, preleasing, multi-phase districts and cancellation of a funded build remain later scope. Specialized production machines remain in existing business equipment accounting; this update exposes the property's installed equipment system rather than creating a machine inventory. Repair capacity is tracked in effective work minutes, not a physical minute-by-minute crew scheduler. These are game rules, not real licensing or property law.
