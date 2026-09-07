#!/bin/bash
# Installed on Unraid, not fetched or executed from a registry image.
# Only the tested GHCR main channel is eligible for unattended deployment.
set -Eeuo pipefail
umask 077

root="${EMPIRE_APP_ROOT:-/mnt/user/appdata/econgame}"
[[ "$root" = /* && "$root" != / && "$root" != */ && ! -L "$root" ]] || exit 2
root=$(realpath "$root")
source_dir="$root/source"
data="$root/data"
state="$root/deploy"
repository=ghcr.io/computernerder/econgame
channel="$repository:main"
name=econgame
qa=econgame-update-check
mkdir -p "$state"
exec 9>"$state/update.lock"
flock -n 9 || exit 0
[[ -f "$state/enabled" && ! -f "$state/paused" ]] || exit 0
[[ -d "$data" && ! -L "$data" && -f "$source_dir/compose.yaml" && -f "$source_dir/.env" ]] || { echo 'Missing deployment files or unsafe data path.' >&2; exit 2; }
cd "$source_dir"
unset EMPIRE_IMAGE
compose() { docker compose -p econgame "$@"; }
log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }
if [[ -f "$state/update.log" ]] && (( $(stat -c %s "$state/update.log") > 1048576 )); then
    mv -f "$state/update.log" "$state/update.log.1"
fi

# Fail closed if the operator has changed the container or storage arrangement.
config=$(compose config --format json)
[[ $(jq -r '.services.econgame.container_name' <<<"$config") = "$name" ]] || exit 2
mount=$(jq -r '.services.econgame.volumes[] | select(.target == "/data") | .source' <<<"$config")
[[ "$mount" = "$data" ]] || { log 'Data mount differs from expected appdata/data; update skipped.'; exit 2; }
user=$(jq -r '.services.econgame.user' <<<"$config")
[[ "$user" =~ ^[0-9]+:[0-9]+$ ]] || exit 2
origin=$(jq -r '.services.econgame.environment.EMPIRE_PUBLIC_URL' <<<"$config")
current=$(docker inspect "$name")
[[ $(jq -r '.[0].State.Running' <<<"$current") = true ]] || { log 'Game is stopped; update skipped.'; exit 0; }
old_image=$(jq -r '.[0].Image' <<<"$current")
[[ "$old_image" =~ ^sha256:[a-f0-9]{64}$ ]] || exit 2

# Pull completes before stopping the game; registry/network failures cause no downtime.
if ! pull_result=$(docker pull --quiet "$channel" 2>&1); then
    log "Cannot pull $channel. Make the GitHub container package public, or authenticate Docker with read:packages."
    exit 1
fi
image=$(docker image inspect "$channel")
candidate=$(jq -r --arg repo "$repository@" '.[0].RepoDigests[] | select(startswith($repo))' <<<"$image" | head -1)
[[ "$candidate" =~ ^ghcr\.io/computernerder/econgame@sha256:[a-f0-9]{64}$ ]] || exit 2
new_id=$(jq -r '.[0].Id' <<<"$image")
[[ "$new_id" = "$old_image" ]] && exit 0
[[ ! -f "$state/failed-digest" || $(cat "$state/failed-digest") != "$candidate" ]] || exit 0
build=$(jq -r '.[0].Config.Labels["io.econgame.build-number"]' <<<"$image")
revision=$(jq -r '.[0].Config.Labels["org.opencontainers.image.revision"]' <<<"$image")
[[ $(jq -r '.[0].Config.Labels["org.opencontainers.image.source"]' <<<"$image") = https://github.com/computernerder/econgame ]] || exit 2
[[ "$build" =~ ^[1-9][0-9]*\.[1-9][0-9]*$ && "$revision" =~ ^[a-f0-9]{40}$ ]] || { log 'Image has no valid GitHub build identity; skipped.'; exit 2; }
old_build=$(jq -r '.[0].Config.Labels["io.econgame.build-number"] // "local"' <<<"$current")
if [[ "$old_build" =~ ^[1-9][0-9]*\.[1-9][0-9]*$ ]]; then
    old_run=${old_build%.*}; new_run=${build%.*}
    old_attempt=${old_build#*.}; new_attempt=${build#*.}
    if (( new_run < old_run || (new_run == old_run && new_attempt <= old_attempt) )); then
        log "Ignoring older build $build; running $old_build."
        exit 0
    fi
fi

backup="$root/backups/build-$build-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup"
cp -p .env "$backup/env-before"
printf '%s\n' "$old_image" > "$backup/image-before"
phase=running
qa_started=false
wait_healthy() {
    local target=$1 attempt
    for attempt in $(seq 1 "${EMPIRE_HEALTH_ATTEMPTS:-30}"); do
        if docker exec "$target" python -m economic_simulation.server --healthcheck >/dev/null 2>&1; then return 0; fi
        [[ $(docker inspect --format '{{.State.Running}}' "$target") = true ]] || return 1
        sleep "${EMPIRE_HEALTH_INTERVAL:-2}"
    done
    return 1
}
record_image() {
    # Retain every other operator setting, including the public URL and data directory.
    local selected=$1
    awk '!/^EMPIRE_IMAGE=/' .env > "$state/env-next"
    printf 'EMPIRE_IMAGE=%s\n' "$selected" >> "$state/env-next"
    cat "$state/env-next" > .env
    rm -f "$state/env-next"
}
failed() {
    local code=${1:-1}
    trap - ERR INT TERM
    set +e
    log "Build $build failed during $phase; restoring service. Backup: $backup"
    printf '%s\n' "$candidate" > "$state/failed-digest"
    if [[ "$qa_started" = true ]]; then docker rm -f "$qa" >/dev/null 2>&1; fi
    if [[ "$phase" = starting ]]; then
        # Keep the candidate's possibly migrated saves; never downgrade them in place.
        if ! compose stop "$name"; then log 'Could not stop candidate; manual recovery needed.'; exit 1; fi
        if ! compose rm -f "$name"; then log 'Could not remove candidate; manual recovery needed.'; exit 1; fi
        if ! mv "$data" "$backup/failed-data"; then log 'Could not preserve candidate data; manual recovery needed.'; exit 1; fi
        if ! tar -xzf "$backup/data-before.tar.gz" -C "$root"; then log 'Could not restore backup; manual recovery needed.'; exit 1; fi
        cp -p "$backup/env-before" .env
        record_image "$old_image"
        if ! compose up -d --no-build "$name"; then log 'Old container could not start; manual recovery needed.'; exit 1; fi
    elif [[ "$phase" != running ]]; then
        docker start "$name" >/dev/null
    fi
    if wait_healthy "$name"; then log 'Previous game is healthy; failed build is blocked from automatic retries.'; fi
    exit "$code"
}
trap 'failed $?' ERR
trap 'failed 130' INT TERM

log "Deploying build $build ($revision); stopping at a saved-day boundary."
phase=stopping
compose stop "$name"
phase=backup
tar -czf "$backup/data-before.tar.gz" -C "$root" data
tar -tzf "$backup/data-before.tar.gz" >/dev/null

# Boot against a private copy before touching the live saves. No published port.
phase=preflight
mkdir "$backup/preflight"
tar -xzf "$backup/data-before.tar.gz" -C "$backup/preflight"
docker run -d --name "$qa" --user "$user" --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m --network none \
    --cap-drop ALL --security-opt no-new-privileges:true \
    -e "EMPIRE_PUBLIC_URL=$origin" \
    --mount "type=bind,src=$backup/preflight/data,dst=/data" "$candidate" >/dev/null
qa_started=true
wait_healthy "$qa"
docker stop "$qa" >/dev/null
docker rm "$qa" >/dev/null
qa_started=false

phase=starting
record_image "$candidate"
compose up -d --no-build "$name"
wait_healthy "$name"
jq -n --arg build "$build" --arg revision "$revision" --arg image "$candidate" \
    --arg backup "$backup" --arg date "$(date -u +%FT%TZ)" \
    '{build:$build,revision:$revision,image:$image,backup:$backup,deployed_at:$date}' > "$state/deployed.json"
phase=running
trap - ERR INT TERM
log "Build $build is healthy. Refresh the game to see the updated build badge."
# Backups are intentionally retained. The operator decides their retention policy.
