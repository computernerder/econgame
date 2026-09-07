#!/bin/sh
# Run from a source checkout on Unraid. All persistent state lives in appdata.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
image="econgame:0.34.0"
name="${EMPIRE_CONTAINER_NAME:-econgame}"
data="${EMPIRE_DATA_DIR:-/mnt/user/appdata/econgame/data}"
port="${EMPIRE_HOST_PORT:-8892}"
address="${EMPIRE_BIND_ADDRESS:-0.0.0.0}"
url="${EMPIRE_PUBLIC_URL:-http://192.168.1.3:$port}"
uid="${PUID:-99}"
gid="${PGID:-100}"
case "$data" in /mnt/*) ;; *) echo 'Choose an absolute data path under /mnt.' >&2; exit 1 ;; esac
if docker container inspect "$name" >/dev/null 2>&1; then
    echo "Container $name already exists; see docs/DOCKER_UNRAID_034.md for the stop/replace update procedure." >&2
    exit 1
fi
# Only create/chown a new directory. Existing appdata ownership is not rewritten.
if [ ! -d "$data" ]; then install -d -m 0770 -o "$uid" -g "$gid" "$data"; fi
docker build -t "$image" .
docker run --rm --user "$uid:$gid" --entrypoint python \
    --mount "type=bind,src=$data,dst=/data" "$image" \
    -c 'from pathlib import Path; import tempfile; f=tempfile.TemporaryFile(dir="/data"); f.close(); print("Persistent data directory is writable.")'
docker run -d --name "$name" --restart unless-stopped --init \
    --user "$uid:$gid" --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --cap-drop ALL --security-opt no-new-privileges:true --stop-timeout 60 \
    -p "$address:$port:8000" \
    -e "EMPIRE_PUBLIC_URL=$url" -e EMPIRE_DATA_DIR=/data -e "TZ=${TZ:-America/New_York}" \
    --mount "type=bind,src=$data,dst=/data" \
    --label org.opencontainers.image.source=https://github.com/computernerder/econgame \
    --label 'net.unraid.docker.webui=http://[IP]:[PORT:8000]' "$image"
printf 'Starting Empire Manager at %s\nSign-in key: %s/access-key\nCheck readiness with: docker inspect --format '\''{{.State.Health.Status}}'\'' %s\n' "$url" "$data" "$name"
