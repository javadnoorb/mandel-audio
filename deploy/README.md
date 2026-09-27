# Rendering on a Vultr VM

The reactive-video renderer (`mandel-audio video`) is CPU-bound and scales
across cores via `--workers` (see `mandel_audio/reactive.py`) -- it does
**not** use the GPU, so this is about getting more CPU cores for a render,
not about GPU acceleration. (The [web explorer](../web/) is the GPU-based
part of this project, and a separate thing: it's for interactively finding
a coordinate, not for producing the final video.)

The intended flow:

1. Explore in the [web explorer](../web/) and use its **copy coords**
   button to grab a point (`x: ..., y: ..., scale: ...`).
2. Spin up a VM here, render with that coordinate and a music file, pull
   the video back down.
3. Destroy the VM -- there's no state worth keeping between renders.

## Quick path: one command

Install [`vultr-cli`](https://github.com/vultr/vultr-cli) and point it at
your API key (`~/.vultr-cli.yaml` with `api-key: ...`, or the
`VULTR_API_KEY` env var), then:

```bash
deploy/deploy.sh
```

This creates the VM, hardens it, and installs mandel-audio into a venv --
no other manual steps. It prints the exact `scp`/`ssh` commands for
uploading your music file, rendering, and downloading the result.

Tear down with `deploy/vultr-vm.sh destroy` (see step 5 below) once you
have the file -- you're billed while the VM is running, and there's
nothing worth keeping on it between renders.

## Manual path (step by step)

Useful if you want more control, or to debug a step in isolation.
`deploy/deploy.sh` is just these steps chained together over SSH.

### 1. Create the VM

```bash
deploy/vultr-vm.sh create
```

Provisions an 8 vCPU / 16GB `vc2-8c-16gb` instance in `ewr` (New Jersey)
running Ubuntu 24.04 LTS, uploading/reusing an SSH key named
`<hostname>-mandel-audio` from `~/.ssh/id_ed25519.pub`. Prints the VM's IP
and records the instance ID in `deploy/.vultr-instance-id` (not committed)
so `destroy` can find it later.

**Sizing:** `--workers` scales render time roughly linearly with core
count, so more cores = faster renders, at proportionally higher hourly
cost. Override the plan with `PLAN=vc2-16c-32gb deploy/vultr-vm.sh create`
(or any other plan code) -- Vultr plan codes and pricing change, so check
current ones with `vultr-cli plans list` rather than trusting a number
here. The default is a reasonable middle ground for a single render; for
a long (many-minute) video or a tight deadline, size up.

### 2. Harden the VM

```bash
ssh root@<vm-ip> 'bash -s' < deploy/harden-vm.sh
```

Creates a non-root `deploy` user (with your SSH key and passwordless
sudo), disables root SSH login and password authentication, and enables
`ufw` (SSH only -- this box runs no web service), `fail2ban`, and
unattended security updates. From this point on, log in as
`deploy@<vm-ip>`, not `root`.

### 3. Install mandel-audio

```bash
ssh deploy@<vm-ip> 'bash -s' < deploy/setup-vm.sh
```

Installs system packages (Python, ffmpeg, build tools), clones the repo,
and `pip install`s it into a venv at `~/mandel-audio/.venv`. Prints the
exact commands for the next two steps once done.

### 4. Render

Upload your music file (run **locally**, not on the VM):

```bash
scp your-track.mp3 deploy@<vm-ip>:~/mandel-audio/
```

SSH in and render, using every core and the coordinates from the web
explorer's "copy coords" button:

```bash
ssh deploy@<vm-ip>
cd mandel-audio && source .venv/bin/activate
mandel-audio video -x <cx> -y <cy> --audio-file your-track.mp3 \
  --start-scale 0 --end-scale 15 --workers $(nproc) --youtube -o zoom.mp4
```

`--youtube` re-encodes to YouTube's recommended bitrate/audio settings for
`-N`'s resolution -- see `mandel-audio video --help` for the full option
list (deep zoom past `--end-scale`, beat-punch strength, iteration ramp,
etc.).

Download the result (run **locally**):

```bash
scp deploy@<vm-ip>:~/mandel-audio/zoom.mp4 .
```

### 5. Tear down

```bash
deploy/vultr-vm.sh destroy
```

There's no cache or state worth snapshotting here (unlike a hosted app) --
just destroy it and re-run steps 1-3 next time.

## Not included here

Uploading the finished video to YouTube is a separate, not-yet-built step
(it needs a Google API OAuth setup) -- for now, download the file and
upload it yourself. Ask if you want that automated too.
