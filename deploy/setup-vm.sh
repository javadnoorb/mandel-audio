#!/usr/bin/env bash
# Set up mandel-audio on a hardened Vultr instance (run harden-vm.sh first).
# Usage: ssh in as the deploy user, then run this script.
#
# Unlike a hosted web app, this VM runs no service -- it's just a compute
# box you SSH into to render a video, then scp the result back off. No
# Docker, no reverse proxy, no HTTPS.
set -euo pipefail

REPO_URL="https://github.com/javadnoorb/mandel-audio.git"
REPO_DIR="$HOME/mandel-audio"

echo "==> Installing system packages..."
sudo apt-get update -qq
# python3-venv/pip for the package itself; ffmpeg + libsndfile1 as a system
# fallback (imageio-ffmpeg/soundfile normally bundle their own, but having
# the system libs too avoids surprises on a fresh box); build-essential in
# case any dependency needs to compile from source.
sudo apt-get install -y -qq python3 python3-venv python3-pip git \
  ffmpeg libsndfile1 build-essential

echo "==> Cloning/updating the repo..."
if [ -d "$REPO_DIR" ]; then
  git -C "$REPO_DIR" pull
else
  git clone "$REPO_URL" "$REPO_DIR"
fi

cd "$REPO_DIR"

echo "==> Setting up the Python environment..."
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip -q
pip install -e ".[dev]" -q

cores=$(nproc)
cat <<EOF

mandel-audio is installed at $REPO_DIR ($cores cores available).

Activate the environment:
  cd $REPO_DIR && source .venv/bin/activate

Upload a music file from your machine (run locally, not on the VM):
  scp your-track.mp3 deploy@<vm-ip>:~/mandel-audio/

Render a video, using every core (from the coordinates you picked in the
web explorer -- see its "copy coords" button):
  mandel-audio video -x <cx> -y <cy> --audio-file your-track.mp3 \\
    --start-scale 0 --end-scale 15 --workers $cores --youtube -o zoom.mp4

Download the result back to your machine (run locally, not on the VM):
  scp deploy@<vm-ip>:~/mandel-audio/zoom.mp4 .

See deploy/README.md for full option/plan-sizing notes, and remember to
destroy the VM (deploy/vultr-vm.sh destroy) once you have the file --
you're billed while it's running.
EOF
