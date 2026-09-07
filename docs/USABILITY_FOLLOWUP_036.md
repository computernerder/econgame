# Usability study follow-up — 0.36.0

## Behavior

- Warranty claims reject duplicate recovery work and repeated negotiations. New outside or mixed recovery must cost less than the existing claim or rent exposure, including prior actual service costs. Purchased supplier rates count at their real price. Internal recovery checks actual payroll allocation before consuming the next block of hours. Previously queued uneconomic or duplicate work stops on time advance; unused reserves are returned under the existing supplier/refund rules. Actual past expenses remain. Specialist referrals can proceed once to outside counsel.
- The decision inbox shows claim expense, actual recoveries and completed attempts, plus a reviewed action to stop pursuing an unbooked claim. Closing a claim creates neither cash nor a fabricated write-off. Unfinished work must be cancelled first. Overdue service work can be cancelled directly from the inbox. Navigation buttons say where they go, and single response forms are visible.
- Accepted hires cover the opening recruitment requirement while awaiting their start dates. The opening plan shows the expected start date, stale staffing decisions resolve, and this wait does not repeatedly interrupt time. Actual missing roles still stop the skip, and the operation cannot open until required staff become active.
- Building sites describe the funded construction and completion date. Building comparisons and the duplicate construction CTA disappear during work. Asset book cost, original land/prior costs, installed construction, remaining reserved capital and total commitment are separated without double counting.
- Start-a-business controls appear before long tables, with a Home shortcut. Empty/short names receive local field validation; name/number errors no longer suggest unrelated inbox/activity navigation.
- Command forms preserve drafts in this browser tab and campaign. Drafts can be discarded, remain after failed review, and clear only after successful submission. Explicit page/record contexts are separate. No passwords or hidden authority identifiers are persisted in drafts.
- Completed actions show a dismissible fixed success notice even when the browser restores a deep scroll position. Completed job and campaign tables use 15-row paging; all rendered rows remain accessible without JavaScript. Service queues retain older rows and use readable task labels.

## Validation

Twelve new tests exercise recovery affordability, duplicates, prior failure, legacy refunds, real supplier prices, internal labor, claim preview/close, waiting and genuinely missing hires, save/load equivalence, construction reconciliation, and rendered controls. Existing service, property, collection, inbox, navigation, financial and time-skip tests are also run. The delivery entry records final results.

Browser checks use a disposable local campaign: restored business-name draft after reload, native industry selection, table paging, reviewed formation, visible success notification and cleared submitted draft. No player campaign was altered for QA.

## Limits

- A declined warranty negotiation cannot be rerolled. A recorded specialist referral may proceed to outside counsel. There is no owner override to spend more than recovery exposure merely to pursue a principle.
- Existing historical legal costs are not refunded. Only unused prepaid capacity is returned, respecting purchased credit expiry.
- Payroll continues for employed internal staff; stopping an uneconomic task prevents more cost allocation and frees capacity, rather than manufacturing cash savings.
- Drafts last for the browser tab/campaign session, not across devices. Review always rechecks current eligibility and funding.
- Table paging is client-side. Some pre-existing report history limits remain; this is not a database pagination redesign.
- Native dropdowns were exercised successfully in the preview; the study's intermittent missed-click behavior was not reproduced.

Next: use the updated game to assess whether routine exceptions need further tuning, while preserving required approvals and financial guardrails.

## Local release validation

The combined 204-test affected suite passed 203 tests and exposed one stale static-asset version assertion. The asset version was corrected and the affected context-form tests were rerun. Twelve new regression tests and browser checks passed. Complete GitHub validation and deployment are recorded after publication.

## Live delivery — 2026-09-07

All 844 tests passed in GitHub Actions run 34148207649 (242, 193, 220 and 189 across the four shards). The packaged container startup check and image publication passed.

Build 3.1, code revision aa3b795881d6df35486f7ab2cc47d0c2e6ce04d8, deployed through the guarded Unraid updater at 17:40:13 UTC. Image digest: sha256:0eca9189658d9ae33b3f96b2cef1a5fa2c8fc445361d8cf8718861d27c2bed55. Saved-game backup: /mnt/user/appdata/econgame/backups/build-3.1-20260907T174004Z.

Normal browser sign-in and the saved campaign's Portfolio overview were verified at http://game.lan, including Build 3.1 / v0.36.0, the new Start a business shortcut and the new UI script. The disposable local preview server was stopped. Existing player campaigns were not modified for QA.
