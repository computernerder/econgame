# Live Unraid deployment — 2026-09-07

- Game URL: http://192.168.1.3:8892
- Release: 0.34.0; image `econgame:0.34.0` built successfully on the target Unraid server.
- Container: `econgame`, managed by Compose project `econgame`, with restart policy `unless-stopped`.
- Source export: `/mnt/user/appdata/econgame/source`. This is a Git archive export, not a Git checkout; update it from a new source export before rebuilding.
- Persistent volume: `/mnt/user/appdata/econgame/data` mounted at `/data`; application UID 99/GID 100.
- Access key: `/mnt/user/appdata/econgame/data/access-key`. A local copy is at `C:/Projects/EconmicSimulationGame/saves/unraid-access-key.txt`. Credentials and campaigns are excluded from Git.
- Three desktop campaigns were copied with explicit approval. The desktop originals remain independent and unchanged. Earlier save formats were upgraded in the copies using the existing migrations.

The live container reported healthy. Sign-in and anonymous-access protection passed. Eight authenticated pages rendered: My games, Businesses, Properties, Employees, Finances, Decision inbox, Management and Home office. Canonical saved-state hashes for all three server campaigns matched the checked import copies. Acceptance checks executed no game commands in the live library.

The 103 targeted tests and separate Linux container tests are described in [the deployment guide](DOCKER_UNRAID_034.md). A temporary QA container verified commands, campaign switching, restart persistence and Linux save locking before live deployment.

Future work starts in the SSH-backed Git repository on the development PC. Keep `/data` separate from source exports and images. Update only this application's container and files; unrelated Unraid services were not changed.
