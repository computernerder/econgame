# Remove vacancies — 0.17.1

Open a business, expand **Advanced vacancies and hiring**, select **Vacancy to remove**, and choose **Remove vacancy**. The existing review dialog explains the impact before committing. Removal has no charge and does not dismiss an employee or cancel an accepted offer.

Vacancies are archived in the saved `systems.closed_positions` registry. Stable position IDs and former employment records remain available for history and payroll attribution. Old saves without this registry work unchanged. Position creation still uses monotonically increasing IDs; archived positions do not count toward the 100-position limit.

Reporting positions move to the removed position's supervisor, or company leadership. Hiring/promotion/reporting commands reject stale references to closed positions. Business staffing, guided hiring, reporting choices, organization charts, and delegated hiring all exclude closed positions. Explicit manager staffing targets fall by one where possible, without increasing a lower target or reducing it below existing occupied staff. Open/deferred hiring approvals for this specific position are cancelled and retained in the audit history.

Removing a vacancy does not waive industry staffing requirements, end recruitment campaigns already purchased, or disable separately authorized growth. A player can create a new position again. This release does not add an archive restoration screen.

Validation:

- Sixteen dedicated tests cover persistence and idempotency, no cash or employment changes, former employees, reporting repair, active/joining/seller safeguards, ownership, stale hire/promotion/reporting commands, open/deferred approval cancellation, manager vacancy/growth policies, preview and command endpoints, old saves, and more than 100 create/remove cycles.
- Dedicated tests plus navigation and organization regression: 26 passed.
- Browser check on a disposable copy of the current campaign: removed Northbank Engineering's technician vacancy, observed zero remaining vacancies and unchanged $290,450.79 cash. Live campaign was not edited.
- Full regression suite: 332 passed in 174.08 seconds, with two existing dependency deprecation warnings. Source-only installation includes a backup; per-file hashes and installed-page smoke checks are recorded in the release receipt.
