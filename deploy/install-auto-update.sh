#!/bin/bash
# Unraid's built-in cron loader includes custom files in dynamix/*.cron.
set -euo pipefail
[[ $(id -u) = 0 && -x /usr/local/sbin/update_cron && -d /boot/config/plugins/dynamix ]] || {
    echo 'Run this installer as root on Unraid.' >&2; exit 1;
}
[[ ${1:-} = '' || ${1:-} = --enable ]] || { echo 'Usage: install-auto-update.sh [--enable]' >&2; exit 2; }
root=/mnt/user/appdata/econgame
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
[[ -f "$root/source/.env" && -d "$root/data" ]] || { echo 'Existing game deployment not found.' >&2; exit 1; }
grep -q 'EMPIRE_IMAGE' "$root/source/compose.yaml" || { echo 'Update compose.yaml to the image-override version first.' >&2; exit 1; }
install -d -m 700 "$root/deploy"
if [[ -f "$root/deploy/update-unraid.sh" ]]; then
    cp -p "$root/deploy/update-unraid.sh" "$root/deploy/update-unraid.before-$(date +%Y%m%d%H%M%S).sh"
fi
install -m 700 "$here/update-unraid.sh" "$root/deploy/update-unraid.sh"
cat > /boot/config/plugins/dynamix/econgame-update.cron <<'CRON'
# Empire Manager: pull only successful GitHub main builds. Settings: appdata/econgame/deploy.
*/5 * * * * /bin/bash /mnt/user/appdata/econgame/deploy/update-unraid.sh >> /mnt/user/appdata/econgame/deploy/update.log 2>&1
CRON
chmod 600 /boot/config/plugins/dynamix/econgame-update.cron
if [[ ${1:-} = --enable ]]; then touch "$root/deploy/enabled"; fi
/usr/local/sbin/update_cron
echo 'Five-minute update schedule installed and persistent across Unraid restarts.'
echo 'Enable: touch /mnt/user/appdata/econgame/deploy/enabled'
echo 'Pause: touch /mnt/user/appdata/econgame/deploy/paused'
echo 'Resume: remove only /mnt/user/appdata/econgame/deploy/paused'
echo 'Status: cat /mnt/user/appdata/econgame/deploy/deployed.json'
