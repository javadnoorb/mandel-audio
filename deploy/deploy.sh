#!/usr/bin/env bash
# End-to-end: create the VM, harden it, and install mandel-audio -- a single
# command instead of the manual multi-step flow.
#
# Usage:
#   deploy/deploy.sh
#
# When it finishes you have a ready-to-render box; it prints the exact scp/
# ssh commands for uploading a music file, rendering, and downloading the
# result.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_USER="${DEPLOY_USER:-deploy}"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=8)

echo "==> Creating VM..."
ip=$("$SCRIPT_DIR/vultr-vm.sh" create)
echo "VM IP: $ip"

echo "==> Waiting for SSH..."
for _ in $(seq 1 30); do
  ssh "${SSH_OPTS[@]}" -o BatchMode=yes "root@$ip" true 2>/dev/null && break
  sleep 5
done

echo "==> Hardening..."
ssh "${SSH_OPTS[@]}" "root@$ip" 'bash -s' < "$SCRIPT_DIR/harden-vm.sh"

echo "==> Installing mandel-audio..."
ssh "${SSH_OPTS[@]}" "$DEPLOY_USER@$ip" 'bash -s' < "$SCRIPT_DIR/setup-vm.sh"

cat <<EOF

==> Done. VM ready at $ip.

Upload a music file:
  scp your-track.mp3 $DEPLOY_USER@$ip:~/mandel-audio/

Render (SSH in first):
  ssh $DEPLOY_USER@$ip
  cd mandel-audio && source .venv/bin/activate
  mandel-audio video -x <cx> -y <cy> --audio-file your-track.mp3 \\
    --start-scale 0 --end-scale 15 --workers \$(nproc) --youtube -o zoom.mp4

Download the result:
  scp $DEPLOY_USER@$ip:~/mandel-audio/zoom.mp4 .

Destroy the VM when you're done (you're billed while it's running):
  $SCRIPT_DIR/vultr-vm.sh destroy
EOF
