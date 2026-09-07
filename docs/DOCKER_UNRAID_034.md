# Docker and Unraid — 0.34.0

The headless server runs the existing simulation and multiple-game library. It does not open a desktop window or install Windows GUI runtimes. The desktop launcher continues to use its loopback-only session.

## Deployment on 192.168.1.3

Use the existing Unraid Docker service. The intended address is **http://192.168.1.3:8892**, mapped to container port **8000**. Persistent state belongs at **/mnt/user/appdata/econgame/data**, mounted at **/data**. This follows Unraid's [appdata and port-mapping model](https://docs.unraid.net/unraid-os/using-unraid-to/run-docker-containers/managing-and-customizing-containers/).

From an up-to-date source checkout on Unraid:

```sh
install -d -m 0770 -o 99 -g 100 /mnt/user/appdata/econgame/data
cp .env.example .env
# Review .env, especially the public URL and port, before the first start.
docker compose up -d --build
docker compose logs --tail 30 econgame
docker inspect --format '{{.State.Health.Status}}' econgame
```

On an existing data directory, check ownership before changing anything. UID 99/GID 100 is the Unraid `nobody/users` account used by this configuration. The image normally runs as UID/GID 10001 for a named Docker volume; `.env.example` selects Unraid's account for its bind mount. The container runs without root, with a read-only application filesystem and a writable `/data` volume.

If Docker Compose is unavailable, `sh deploy/unraid.sh` builds and creates the equivalent container. It checks data-directory write access and refuses to replace a pre-existing container. It does not require Docker Desktop. For first-time source retrieval, use `git clone git@github.com:computernerder/econgame.git` with a GitHub-authorized server SSH key, or transfer the source over SSH from the existing checkout. Never copy a private SSH key into the image.

## Sign in

The first start generates a random access key at `/data/access-key`. Read it in the Unraid terminal:

```sh
docker exec econgame cat /data/access-key
```

Open the game address and enter that key. It persists across container replacement. The game HTML contains a separate random session/CSRF token, not the server access key. Sign-in cookies last up to 12 hours in the browser, and a server restart requires signing in again. Sign out is in the navigation menu. Repeated failed logins are limited, and only the configured host and origin are accepted for game actions.

For external secret management, set either `EMPIRE_ACCESS_KEY` or `EMPIRE_ACCESS_KEY_FILE` when creating the container. Use at least 16 characters. The default generated key avoids placing credentials in Compose files, image layers or application logs. To rotate it, replace the contents of the generated key file while retaining its ownership/permissions, then restart the container.

## Games and persistence

- `/data/saves/` contains campaigns and their recovery backups.
- `/data/saves/last-campaign.txt` selects the game resumed after restart.
- `/data/access-key` contains the generated sign-in credential.
- `/data/.server.lock` prevents a second server process from opening the same library, including after switching campaigns. Each active campaign also has its own OS lock.

Everyone signed in shares the library, the current campaign and its decisions. A campaign switch is visible to other browsers; stale revisions and campaign-session IDs are rejected. For separate players, use separate containers with separate data paths, host ports and public URLs. Inactive campaigns do not advance.

To import desktop progress, stop the desktop game and copy its campaign `.sqlite3` files and `last-campaign.txt` into `/data/saves/` while the server is stopped. A live-copy workflow must use SQLite's backup API to create consistent snapshots. Do not copy a live database as an ordinary file. Keep original desktop files as a backup. Existing migration and financial-audit checks run when a copied game opens.

Back up the entire data directory with the container stopped. Container/image removal does not remove a bind-mounted appdata directory. Do not use `docker compose down -v` with a named volume unless deleting its campaigns is intended.

## Updates and network settings

Update the source, then run `docker compose up -d --build`. Compose stops/replaces the old container; the existing bind mount is reused. With the standalone script, stop and remove only the old container before rerunning it:

```sh
docker stop --time 60 econgame
docker rm econgame
sh deploy/unraid.sh
```

Keep the previous source/image and a stopped-container data backup for rollback. Save upgrades can make a newer database unsuitable for older code. Never run two writers against the same data folder.

`EMPIRE_PUBLIC_URL` is the exact address users open, including any non-default port. `EMPIRE_HOST_PORT` sets the published port; `EMPIRE_BIND_ADDRESS` selects the host interface. After changing the public URL, recreate/restart the server. Multiple aliases and URL subpaths are not supported in this release.

For HTTPS, terminate TLS at a reverse proxy, preserve the original Host header, and set the public URL to that HTTPS origin. Cookies then use Secure. The server does not trust arbitrary forwarded headers. Use HTTPS or a private VPN when providing access beyond a trusted LAN; the basic HTTP deployment here is for the local network.

## Validation and limits

Targeted validation: **103 tests passed**: 54 covering network sign-in, host/origin/CSRF checks, throttling, sign-out, secure cookies, two-browser conflicts, persistent campaign selection and credentials, whole-library locking, graceful shutdown, existing desktop routes and saved-game behavior; 49 covering navigation, quieter skips and the HTTP command-ID fallback. The fallback was tested with 1,000 unique valid UUIDs while `crypto.randomUUID` was unavailable. Existing Starlette/AnyIO deprecation warnings remain.

The Linux image built successfully on Unraid 6.12.8 / Docker 24.0.9. A separate disposable container ran as UID 99/GID 100 with a read-only application filesystem. Real LAN HTTP checks passed for sign-in, commands, campaign creation/switching and restart persistence; the Docker health check reported healthy. Chrome rendered the LAN sign-in page, but an extension popup prevented the remaining interactive browser steps. The local Docker Desktop engine was recovered from an unreadable temporary endpoint; its local image build encountered a host certificate-trust problem, so the completed image build and container validation ran on Unraid.

A Linux process-level probe also confirmed that the running container rejects a second writer to its library. Desktop campaign snapshots passed SQLite integrity checks, preserved balances and existing employee identities, and reconciled before import. Original desktop save files were not modified.

The server is a single game instance with shared administrator access. There are no individual user accounts, permission levels or independent simultaneous player sessions. One process owns the library; do not add Uvicorn workers or replicas. The simulation rules, seeded outcomes and save schema are unchanged by this release.
