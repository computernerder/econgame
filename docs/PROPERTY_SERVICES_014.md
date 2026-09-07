# Property service businesses — 0.14.0

Open **Property services** beneath the cash header. Cleaning, landscaping and security companies are available to acquire or start, with normal ownership, employees, hiring guidance, development, accounting, management and closure rules. A personal property owner can simply buy outside visits; no headquarters or service subsidiary is required.

## Delivered simulation

| Industry | Staffing and constraints | Income and property work |
| --- | --- | --- |
| Cleaning | Cleaners and management; finite equipment capacity, condition, travel and consumables | Qualified outside work is invoiced with 14-day terms. Completed property visits restore cleanliness. |
| Landscaping | Gardeners and management; equipment, materials, local wet weather and reduced winter demand | Outside customer work competes with grounds visits. Weather may postpone either; completed visits restore grounds presentation. |
| Security | Guards with current security credentials and management; equipment, consumables and travel | Outside work is invoiced. Completed patrols provide recent coverage against property vandalism risk; coverage expires and cannot guarantee prevention. |

Regional demand, competition, pricing, customer relationships, wages, equipment condition and cash constrain operation. Outside collections use the existing delayed/defaulting invoice model. Unpaid staff and suppliers enter the existing distress system. Local improvements, training, pricing, schedule changes, support services and debt repayment remain available within a single company. No acquisition of unrelated industries is required.

Property plans contain 1–20 visits, their cadence, priority, property, payer, provider, estimated qualified effort, deadline and full prepaid cost. Larger properties require more time. Owned providers use the same qualified worker pool as outside customers: service work and 30-minute local or 90-minute cross-region travel consume capacity first, in priority/deadline order. Supplies require cash before work releases the customer's prepaid payment. A company with no available qualified workers or supply cash cannot deliver.

Outside contractors deliver up to four qualified hours per plan each weekday. Landscaping also checks weather at the target property. Cadence starts after each completed visit, so delays accumulate and can breach the deadline. Completed visits change the property; booking or partial work does not instantly grant the completed result. The digest and service screen retain progress, expense, unused reserve, refunds and outcomes.

Cleanliness declines with use, and grounds deteriorate over time. Presentation affects both ordinary single-home rental offers and negotiated space offers; poor presentation also lowers the renewal ceiling. Existing contracted rent stays fixed. These services do not repair structural systems or guarantee appreciation. Existing repair and renovation workflows remain separate.

Property vandalism is evaluated monthly from the property's region and a seeded property/date outcome, whether or not the player has purchased security. Actual incidents create cleanup payables and damage grounds presentation. Recent completed patrols reduce the probability, with a minimum residual risk. The screen reports actual coverage-based risk reduction; it does not invent savings from hypothetical prevented incidents. Uncontrolled properties do not interrupt the player's skip.

## Authority, costs and ownership

The owner reserves the complete plan cost in `asset:prepaid_property_services`. Each delivered minute consumes that asset and becomes an expense. An owned contractor receives the released payment as `income:internal_property_services:<owner>`; the owner records the matching internal expense. Both are eliminated in group results; the contractor's actual wages, taxes, benefits, travel capacity and supplies remain real costs. The internal quote is 80% of the outside rate, not a promise that every internal provider is cheaper after actual costs.

Unused reserves are refunded on cancellation. Partial work remains an expense. A property ownership change, provider closure or provider divestment cancels undelivered work and refunds the original payer; a buyer does not silently inherit the service commitment. Service and incident costs are attributed to the property and included in its existing sale/flip project-cost calculation.

The complete prepaid amount goes through existing scope, geography, cumulative authority and cash-reserve checks. Explicitly enabled property-operations automation can propose four cleaning or grounds visits when care is poor. It uses the normal approval boundary; an unauthorized plan never starts because a skip was requested. Automatic outside-customer work requires no separate manual job selection. Manager recruiting now respects role-level licenses as well as explicit position requirements.

## Persistence and tested scope

The migration backs up the save as `before-property-services`, adds missing service businesses, preserves existing employees and accounts, initializes property-care state and advances content compatibility and systems version to 5. Older engines reject the new content. Existing employee identities and reporting relationships are retained. Installation does not run the migration against the player's live campaign; it occurs on the next launch.

See [validation](VALIDATION.md) for executed regressions, campaign-copy browser checks and a 90-day seeded balance sample. Those samples are not a guarantee of profitability across seeds or a decades-long balance certification.

## Limits and next work

External customer work uses a daily demand pool and dated invoices rather than named, negotiable customer contracts. Outside property contractors have per-plan capacity; competing plans do not share a global vendor workforce. Routes use a fixed local/cross-region travel allowance. Property care is represented by two condition measures and recent patrol history, while structural systems remain in the repair model. No permanent department unlock or employee-free internal service is granted.

Internal contractors currently commit to quoted prepaid rates, without a separate contractor-side acceptance negotiation. Automated property-care proposals choose outside contractors; the player selects owned providers when booking plans. Hotels, parking, specialist leasing operations and richer service contracting remain open. Land assembly, feasibility, development approvals, phased construction, financing, preleasing and district improvements remain the next major development sequence. The original design is still broader than this increment.
