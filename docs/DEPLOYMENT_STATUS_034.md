# Live Unraid deployment — 2026-09-07

- Game URL: http://game.lan (Caddy proxy; updated 2026-09-07).
- Release: 0.34.1; image `econgame:0.34.1` built successfully on the target Unraid server.
- Container: `econgame`, managed by Compose project `econgame`, with restart policy `unless-stopped`.
- Source export: `/mnt/user/appdata/econgame/source`. This is a Git archive export, not a Git checkout; update it from a new source export before rebuilding.
- Persistent volume: `/mnt/user/appdata/econgame/data` mounted at `/data`; application UID 99/GID 100.
- Access key: `/mnt/user/appdata/econgame/data/access-key`. A local copy is at `C:/Projects/EconmicSimulationGame/saves/unraid-access-key.txt`. Credentials and campaigns are excluded from Git.
- Three desktop campaigns were copied with explicit approval. The desktop originals remain independent and unchanged. Earlier save formats were upgraded in the copies using the existing migrations.

The live container reported healthy. Sign-in and anonymous-access protection passed. Eight authenticated pages rendered: My games, Businesses, Properties, Employees, Finances, Decision inbox, Management and Home office. Canonical saved-state hashes for all three server campaigns matched the checked import copies. Acceptance checks executed no game commands in the live library.

The 103 targeted tests and separate Linux container tests are described in [the deployment guide](DOCKER_UNRAID_034.md). A temporary QA container verified commands, campaign switching, restart persistence and Linux save locking before live deployment.

Future work starts in the SSH-backed Git repository on the development PC. Keep `/data` separate from source exports and images. Update only this application's container and files; unrelated Unraid services were not changed.

## Caddy address update — 2026-09-07

The game now uses `EMPIRE_PUBLIC_URL=http://game.lan` in the live source `.env`. Caddy's persisted `/mnt/user/appdata/caddy/Caddyfile` contains `http://game.lan { reverse_proxy 192.168.1.3:8892 }`. The backend remains bound to `192.168.1.3:8892`; direct browser access by IP is rejected by the game's hostname check. Use `http://game.lan/login` with the existing access key. Local DNS was verified to resolve game.lan to 192.168.1.3.

The previous game.lan route existed only in Caddy's live configuration and incorrectly targeted 127.0.0.1:8892. All other running Caddy configuration was compared structurally with the saved configuration and preserved. Settings and a stopped-game data archive were backed up under `/mnt/user/appdata/econgame/backups/caddy-game-20260907-082822` before recreation. Docker reports healthy; proxy health, login form, existing-key authentication, and the authenticated game library passed. No game commands were executed during verification.

## Browser sign-in repair � 0.34.1

Network pages now send Referrer-Policy: same-origin. The previous no-referrer policy made native browser form submissions send Origin: null, which the login and logout origin checks rejected. Desktop launcher pages retain no-referrer. Missing, null and foreign origins remain rejected; credentials and CSRF checks are unchanged.

Validation: the final fresh run of tests/test_network_server.py, tests/test_template_updates.py and tests/test_game.py passed all 45 tests with two existing dependency deprecation warnings. An earlier run failed because the versioned template guard had not yet been updated; that guard was corrected before the final run. Native browser login and logout passed on an isolated 0.34.1 container. Native browser login with the existing key then passed on http://game.lan, showing Real Estate Mog at the saved date. No gameplay commands were executed. The temporary QA container was removed.

Image: sha256:0ad0a7985f7cb4ea1f4efb1a274cb95fba1d6970c07d1cc25ab057ab0cb1d833. Production source and stopped-game saves were backed up to /mnt/user/appdata/econgame/backups/login-fix-0341-20260907-084132. The live source export was updated; .env, access key, and data mounts were preserved. The previous 0.34.0 image remains available for rollback.
