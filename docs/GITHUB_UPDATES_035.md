# GitHub builds and automatic Unraid updates

Work in `C:\Projects\EconmicSimulationGame`. Create a feature branch, push it, open a pull request, and merge into `main` after the checks pass. Direct pushes to `main` also run the tests before publication. Every successful main build is published to `ghcr.io/computernerder/econgame`; Unraid checks the `main` image tag every five minutes. No inbound ports, GitHub runner on Unraid, personal access token, or deployment SSH secret are required for the public-package setup.

## One-time GitHub configuration

**Current setup verified:** Actions is enabled, Build 1.1 passed and deployed, the package is anonymously downloadable, and the five-minute checker is installed/enabled. No further configuration is required. The steps below are for recreating the setup.

1. Under **econgame → Settings → Actions → General**, enable Actions. The workflow uses pinned official `actions/checkout`, `actions/setup-python`, and `actions/setup-node` actions. If you restrict allowed actions, allow those. No broad write-default setting is necessary: the publishing job explicitly requests `packages: write` using GitHub's automatic `GITHUB_TOKEN`.
2. Open **Actions → Test and publish**. The first push runs automatically. Wait for all four test shards and **Publish tested image** to pass. The workflow can also be started with **Run workflow → main**. Pull requests never publish images.
3. After the first successful publication, open your GitHub profile's **Packages → econgame → Package settings → Change visibility → Public**. New packages may initially be private; confirm visibility instead of assuming it follows the repository. The source is already public; this makes the built application downloadable without credentials. Saved campaigns, access keys and `.env` files are excluded from the Docker image. Do not make a different private package public.

No repository secrets or variables need to be added. The first private-package pull will fail safely; making the package public lets the next scheduled check proceed. If you deliberately keep the image private, authenticate Docker on Unraid with a classic PAT limited to `read:packages` instead; do not put that token into Git or the game container.

Optional: configure a main-branch ruleset requiring **Tests (0)** through **Tests (3)** before merging. Require pull requests if you want to prevent direct pushes. A single owner does not need a mandatory reviewer just to deploy.

## Visible identity

The badge is directly beneath the Empire Manager logo, above Foundations, and on the login page. `Build 42.2` means workflow run 42, attempt 2. The second line shows the application version and seven-character Git commit. Rerunning an unchanged commit is distinguishable from an earlier attempt. The number comes from the built image, not the current GitHub branch or game save; `Build setup`/`Build local` denotes a manually built image. Responses also carry `X-Empire-Build` for operational checks. Refresh an already-open page after deployment.

## Unraid installation

The current deployment uses `/mnt/user/appdata/econgame/source/compose.yaml`, its existing `.env`, and `/mnt/user/appdata/econgame/data`. Keep `EMPIRE_PUBLIC_URL=http://game.lan`. Caddy and the access key are unchanged.

Install the repository's updated `compose.yaml`, `deploy/update-unraid.sh`, and `deploy/install-auto-update.sh` into that source export. Preserve `.env`. Then, in an Unraid terminal:

```bash
cd /mnt/user/appdata/econgame/source
bash deploy/install-auto-update.sh --enable
```

This installs a fixed controller at `/mnt/user/appdata/econgame/deploy/update-unraid.sh` and a persistent cron entry at `/boot/config/plugins/dynamix/econgame-update.cron`. It uses Unraid's existing `update_cron` loader. It does not install a third-party scheduling plugin or replace other cron entries. Controller/Compose changes are deliberately installed by the operator; an application image cannot replace the deployment controller.

Check immediately, or inspect status:

```bash
bash /mnt/user/appdata/econgame/deploy/update-unraid.sh
cat /mnt/user/appdata/econgame/deploy/deployed.json
tail -50 /mnt/user/appdata/econgame/deploy/update.log
docker inspect --format '{{.Config.Image}} {{.State.Health.Status}}' econgame
```

Pause updates with `touch /mnt/user/appdata/econgame/deploy/paused`. Resume by removing that one marker file. Removing `/mnt/user/appdata/econgame/deploy/enabled` also disables updates. A stopped game is left stopped. Changes do not appear until the full GitHub build completes and the next check succeeds.

## Deployment and failure behavior

The controller locks out overlapping runs, pulls while the current game runs, validates the image's source/build metadata, and pins the exact registry digest. Equal or older build numbers are ignored. It gracefully stops the game, backs up its data and settings, then boots a separate container against a private save copy without publishing any port. Only a healthy preflight proceeds to the live container. Existing operator settings remain intact.

If the live candidate fails its health check, it is stopped. Its possibly migrated data is retained under `failed-data` in the deployment backup, the pre-deployment snapshot is restored, and the previous immutable image is started. No old code is run against newly migrated saves. A failed digest is recorded in `deploy/failed-digest` and not retried automatically. Fix the code and publish a newer build, or deliberately clear that marker to retry after investigation. A restoration/storage failure is logged as requiring manual recovery; the controller cannot guarantee recovery from a broken disk.

Each deployment briefly interrupts access and requires signing in again. The health check covers application startup; it cannot prove every gameplay behavior is correct. Keep the test suite and backups. Backups are retained under `backups/build-*`; unused image layers and backups need periodic operator cleanup. The updater does not prune unrelated Docker images or delete old campaign backups.

## Costs and access

This is a public source repository using standard GitHub-hosted Linux runners. GitHub Container Registry storage/downloads are currently free. No build artifacts or paid runner class are configured. GitHub account billing controls still apply if policies change. The server needs outbound HTTPS access to GitHub Container Registry; browsers continue using `http://game.lan` on the LAN.

Official references: [GitHub image publication](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images), [package visibility](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility), [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
