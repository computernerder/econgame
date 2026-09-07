# Specialist hiring correction — 0.26.3

The "Choose a recognized license requirement" error when creating HVAC, electrical, plumbing or real-estate vacancies was a simulation validation bug. Those roles automatically supplied valid licenses that the older vacancy allowlist rejected. Players had no form choice that could resolve this rejection.

Vacancy creation now accepts all specialist role licenses from the same mapping used by hiring and working-capacity checks. Unknown custom licenses are rejected before creating a position or consuming a position ID. Existing additional engineering and food-safety license requirements remain supported.

The guided hiring page now derives the required license from the selected role even before a vacancy exists, or for an older vacancy with no explicit license field. It displays the requirement and excludes missing/expired licenses using the same rule as the offer action. The page explains that the role sets this requirement automatically. Applicants can be recruited through the existing no-eligible-applicants flow. No license selector is necessary for normal specialist hiring.

Validation: 52 targeted tests passed across specialist hiring (12 new cases), staffing guide, specialists, vacancy removal and workforce. New cases cover actual vacancy creation and hiring for HVAC, electrician, plumber, real-estate agent, HR, legal and accounting; missing/expired license screening before and after vacancy creation; invalid-input atomicity; and the HTTP guided HVAC preview, confirmation, save/load and ledger audit. Existing dependency deprecation warnings remain. No full repository suite or browser visual QA was run.

Industry role availability and qualification requirements are unchanged. This correction does not make HVAC available to every industry or turn the calculated staffing guide into an editable plan. Existing saves need no migration. Restart after installation, then retry creating the specialist vacancy or making the guided offer.
