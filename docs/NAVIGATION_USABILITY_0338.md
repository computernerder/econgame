# Navigation usability — 0.33.8

## Implemented behavior

- Switching the selected company preserves the active tool, including the decision inbox, activity, service reports, home office, forecast, expansion and financing. Detail pages still follow their relevant company or directory.
- Property repairs and property services belong to the Properties section. Home-office tools and financial pages have consistent active navigation labels. Unrelated sidebar groups no longer expand simply because a campaign tool is open.
- Missing businesses, unavailable employees and stale property links show a plain explanation with the appropriate directory. Viewing these pages does not mutate the campaign.
- Small screens have a menu button with the current destination and decision count. All existing destinations remain accessible, and the company tabs fit in two rows.
- Keyboard users can skip directly to the main content. Task links reveal closed sections and move focus to the destination. Escape closes the mobile menu and returns focus to its button.
- The campaign-ending action links directly to the new-game form under My games.

## Validation

The original focused checks passed: 32 navigation, workflow, recovery and campaign tests, plus 20 new navigation regression cases. Desktop and 390-pixel mobile browser checks covered company switching, menu destinations, section highlighting, decision count visibility, task focus and layout overflow; the browser reported no errors.

Final regression: **113 passed**, with two existing dependency deprecation warnings, across navigation, navigation usability, UI workflows, recovery navigation, campaign products, quieter skips, shared resources, department UI and saved-game tests. The rerun completed after disk space became available; the first broader run had been interrupted by a full C: drive while creating temporary saved games. No live saves were modified.

The expanded route audit rendered **35 screens and 171 linked destinations**, with no route errors or missing anchors. It verified that page requests left the copied campaign's simulation state unchanged.

## Limits and next step

This is a navigation update. It does not change simulation behavior, delegated authority, financial rules or save schema. Directory fallbacks cannot restore removed records. Mobile checks cover the tested browser and viewport rather than every device or assistive technology.

The project now uses the SSH GitHub repository. Continue future changes in that checkout, keep campaign data local, and use isolated saves for playtesting. The next usability pass can follow complete workflows with a newly started small business and a larger portfolio, focusing on the decisions that still interrupt delegated play.
