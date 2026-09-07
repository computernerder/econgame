# Multiple games — 0.23.0

Open **My games** at the top of the sidebar. The active game name remains visible while playing.

## Delivered

- Create named, separate Guided, Entrepreneur or Sandbox campaigns with independent world seeds. Existing starting-date and capital restrictions still apply. Creating a campaign retains the current save and opens the new one.
- Browse saved games with their names, owners, simulation dates, personal cash, owned-operation counts, modes, seeds and file timestamps. Existing campaigns receive a readable fallback name without a migration or automatic rename.
- Open another saved game and resume its saved state. Inactive games do not advance. The normal launcher resumes the last campaign opened through the library.
- Rename the active game's display name without moving its file or changing financial and employee identities.
- **Save a copy** duplicates the complete campaign and financial journal for an experiment. The original stays active; open the copy separately when ready. The economic state of the original is unchanged. Request deduplication prevents ordinary retry clicks from creating extra copies.
- Browsing uses read-only SQLite connections and does not run save migrations. Upgrade backups and recovery checkpoints are kept out of the game list. Unreadable files remain in place with an unavailable message.
- File choices are restricted to the current save folder. Missing files, directory traversal and symlinks outside that folder cannot open or create a campaign through the library.
- Switching requires paused simulation. Desktop save locks move to the newly opened game and release the previous game. An already open destination is rejected without replacing the active campaign. Loading audits the selected journal before switching.
- Browser commands carry an active-game session identifier. Stale pages cannot submit decisions, previews or forecasts against another game even when revisions happen to match. Background status refresh directs stale pages to My games. The in-process Python Game API and older API clients retain compatibility; the updated browser supplies the session identifier automatically.

## Validation executed

- Full suite: **427 passed**, two existing dependency deprecation warnings, 207.28 seconds (`qa/full-suite.txt` in staging).
- Final focused library and campaign tests: **22 passed**, 13.65 seconds (`qa/focused-final.txt`), including an added regression for custom dotted filenames.
- Coverage includes independent progression, switching back to exact prior state, copying and journal reconciliation, command retries, pause requirements, lock transfer, locked/corrupt targets, read-only discovery, hidden backups, path validation, escaped names, and stale browser sessions.
- Six pages rendered on an isolated read-only backup of the user's campaign; reading pages preserved world state and the journal audit passed. Browser QA created “Property experiment” from that isolated campaign, verified both entries, and opened the copy with its saved date, finances and active label. Live saves were not modified by QA or installation.

## Current bounds

The library lists campaigns in the active save's folder. Cross-folder import, deletion, cloud synchronization and a backup-restoration interface are outside this increment. Recovery files remain on disk. The earlier handoff and existing simulation features are retained.
