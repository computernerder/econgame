# HR hiring costs — 0.33.1

Hiring an available candidate now uses 60 minutes of completed internal HR work instead of charging the previous reduced $150 recruitment fee. HR payroll remains an operating cost. When the receiving business has fewer than 60 minutes available, outside hiring support still costs $300. The one-month salary cash requirement remains; only the outside fee is paid at acceptance.

The existing dated specialist pool is retained: work comes from real local staff or shared employee assignments, expires after 30 days, and is consumed once. A staff member on leave does not generate new work. Department creation or simply owning another company with an HR employee does not create a permanent free-hiring benefit. Service-queue assignments compete with ordinary specialist work for the same staff hours.

The guided hiring page, advanced vacancy form, confirmation, and recorded hiring history explain the fee and internal HR work. The funding guide and its JavaScript salary calculator use the current quote instead of a fixed $300. The hiring page links to shared HR assignments. Automatic manager hiring uses the same fee function and still checks authority and future wage commitments. Zero-fee hiring creates no artificial expense or cash journal entry.

Separately ordered advertising campaigns, candidate screening, and outsourced service searches retain their existing prices and capacity rules. A role-search project sources candidates; it does not by itself bank an hour of hiring administration for the recipient. Previously charged fees and historical journals are retained. This update changes source only; existing saves need no migration.

Validation executed in an isolated staged copy:

- 99 tests passed across `test_hr_hiring_costs.py`, `test_specialists.py`, `test_staffing_guide.py`, `test_workforce.py`, `test_service_projects.py`, `test_property_scale.py`, `test_leadership.py`, and `test_specialist_hiring.py`.
- The 12 new cases cover exact capacity boundaries, actual cash and payroll, salary reserves, absence, delivered shared work without duplication, expiry, business scope, preview purity, save/load, command idempotence, rejected offers, and both hiring screens.
- Browser QA used an independent SQLite game: the manager hiring guide and review show $0 outside fees, available HR time, salary funding, and the payroll breakdown. Confirmation consumes 60 HR minutes and leaves cash unchanged.
- The full repository suite was not run. Existing FastAPI/Starlette dependency deprecation warnings remain.

Restart the game launcher to load 0.33.1. Next step: play through recruiting in the current campaign; the guide now shows whether the selected business has delivered HR capacity or would pay for outside support.
