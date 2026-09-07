# Live Unraid deployment — 2026-09-07

- Game URL: http://game.lan (Caddy proxy; updated 2026-09-07).
- Release: 0.35.0; GitHub Build 1.1 (cb237e1), automatically deployed from GHCR. Consult deploy/deployed.json on Unraid for subsequent builds.
- Container: `econgame`, managed by Compose project `econgame`, with restart policy `unless-stopped`.
- Deployment files: `/mnt/user/appdata/econgame/source`. This is a source export, not a Git checkout. Application updates now pull tested images from GHCR; install Compose/controller changes explicitly.
- Persistent volume: `/mnt/user/appdata/econgame/data` mounted at `/data`; application UID 99/GID 100.
- Access key: `/mnt/user/appdata/econgame/data/access-key`. A local copy is at `C:/Projects/EconmicSimulationGame/saves/unraid-access-key.txt`. Credentials and campaigns are excluded from Git.
- Three desktop campaigns were copied with explicit approval. The desktop originals remain independent and unchanged. Earlier save formats were upgraded in the copies using the existing migrations.

The live container reported healthy. Sign-in and anonymous-access protection passed. Eight authenticated pages rendered: My games, Businesses, Properties, Employees, Finances, Decision inbox, Management and Home office. Canonical saved-state hashes for all three server campaigns matched the checked import copies. Acceptance checks executed no game commands in the live library.

The 103 targeted tests and separate Linux container tests are described in [the deployment guide](DOCKER_UNRAID_034.md). A temporary QA container verified commands, campaign switching, restart persistence and Linux save locking before live deployment.

Future work starts in the SSH-backed Git repository on the development PC. Keep `/data` separate from source exports and images. Update only this application's container and files; unrelated Unraid services were not changed.

## Caddy address update — 2026-09-07

The game now uses `EMPIRE_PUBLIC_URL=http://game.lan` in the live source `.env`. Caddy's persisted `/mnt/user/appdata/caddy/Caddyfile` contains `http://game.lan { reverse_proxy 192.168.1.3:8892 }`. The backend remains bound to `192.168.1.3:8892`; direct browser access by IP is rejected by the game's hostname check. Use `http://game.lan/login` with the existing access key. Local DNS was verified to resolve game.lan to 192.168.1.3.

The previous game.lan route existed only in Caddy's live configuration and incorrectly targeted 127.0.0.1:8892. All other running Caddy configuration was compared structurally with the saved configuration and preserved. Settings and a stopped-game data archive were backed up under `/mnt/user/appdata/econgame/backups/caddy-game-20260907-082822` before recreation. Docker reports healthy; proxy health, login form, existing-key authentication, and the authenticated game library passed. No game commands were executed during verification.

## Browser sign-in repair — 0.34.1

Network pages now send Referrer-Policy: same-origin. The previous no-referrer policy made native browser form submissions send Origin: null, which the login and logout origin checks rejected. Desktop launcher pages retain no-referrer. Missing, null and foreign origins remain rejected; credentials and CSRF checks are unchanged.

Validation: the final fresh run of tests/test_network_server.py, tests/test_template_updates.py and tests/test_game.py passed all 45 tests with two existing dependency deprecation warnings. An earlier run failed because the versioned template guard had not yet been updated; that guard was corrected before the final run. Native browser login and logout passed on an isolated 0.34.1 container. Native browser login with the existing key then passed on http://game.lan, showing Real Estate Mog at the saved date. No gameplay commands were executed. The temporary QA container was removed.

Image: sha256:0ad0a7985f7cb4ea1f4efb1a274cb95fba1d6970c07d1cc25ab057ab0cb1d833. Production source and stopped-game saves were backed up to /mnt/user/appdata/econgame/backups/login-fix-0341-20260907-084132. The live source export was updated; .env, access key, and data mounts were preserved. The previous 0.34.0 image remains available for rollback.


## Automatic GitHub deployments - 0.35.0

Verified end to end on 2026-09-07: commit cb237e15dece8604d2d12a6bf81522dee1fc76d7 started Test and publish run 34141260384. All four shards of the complete test suite and the image startup/publication job passed. Build 1.1 was published as ghcr.io/computernerder/econgame@sha256:50dfe6739a8d972c844674a6a49be14a23e5a96c3b250b8a9370e6c5695c175e. An anonymous registry manifest request returned 200, so no visibility change or private credential is needed in the current setup.

The controller at /mnt/user/appdata/econgame/deploy/update-unraid.sh pulled, backed up, preflighted and deployed the image successfully. Its record is deploy/deployed.json; the initial backup is backups/build-1.1-20260907T160644Z. Docker reported healthy. Native browser login reached Real Estate Mog and showed Build 1.1 below the logo. No gameplay commands were executed.

The enabled five-minute cron entry is /boot/config/plugins/dynamix/econgame-update.cron, loaded by Unraid update_cron. The .env pins EMPIRE_IMAGE to the current digest and preserves game.lan, port, UID/GID and data settings. Pause with the deploy/paused marker. Backup locations and image digests change with each deployment; consult deploy/deployed.json.

Before the cloud run, 29 Windows network/build/template tests and 14 isolated Linux build/controller tests passed. Controller coverage includes unchanged/older builds, registry failure, invalid identity, backup failure, preflight failure, live rollback preserving failed data, pause and concurrent execution. actionlint and Bash syntax checks passed. Temporary test containers were removed. See docs/GITHUB_UPDATES_035.md for setup and limits.
