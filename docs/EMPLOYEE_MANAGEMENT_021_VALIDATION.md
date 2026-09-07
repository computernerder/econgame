# Employee management 0.21.0 — executed validation

Validated on 6 September 2026 using the project's Python virtual environment, with source staged under `C:\Projects\LearnPython\employee-management-021`.

- Final full suite: **394 passed**, two existing dependency deprecation warnings, **193.46 seconds**. Command: `python -B -m pytest -q`. Output: staging `qa/release-validation.txt`.
- Dedicated new coverage: **22 test cases** in `tests/test_employee_management.py`, including parametrized leave types. These were included in the final full suite.
- Focused employee, business and workforce run: **49 passed** before the final full run.
- Browser walkthrough on a read-only sourced copy of the existing 2028-04-13 campaign: employee directory, benefit/bank summary, dated request preview and submission, inbox approval with coverage warning, approval persistence after restarting the preview server, cross-company supervisor preview and save, and the resulting organization chart.
- Confirmed five vacation days reserved from a 48-day bank, 43 days available, and 40 scheduled hours removed from the upcoming 80-hour two-week schedule. The bank itself was not charged before leave started.
- Confirmed the approved request and supervisor identity survived reload, all current person names were unique and had no digits, and the copied campaign passed its ledger audit. The supervisor change kept the subject's existing employer.
- No live campaign actions were submitted. Installation replaces source, tests and documentation only. The live save upgrades with its own backup on the next restart.

The original review findings about general automatic-project authority and ineligible licensed department staff were not represented as fixed by this employee-management increment. Leave availability is now respected in department delivery, shared assignments and property work, but the wider per-employee resource-allocation improvement remains separate work.

Current limitations and the next increment are documented in `EMPLOYEE_MANAGEMENT_021.md`.
