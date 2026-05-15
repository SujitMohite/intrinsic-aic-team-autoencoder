# Keystone collection — parallel two-machine playbook

Goal: 1500-episode keystone dataset of FastCheatCode demonstrations, collected in parallel across **Machine A** (currently running) and **Machine B** (the other laptop), consolidated on A for training. Targeted at top-30 leaderboard performance (total ≥ 176 across 3 eval trials).

Configs:
- `data_collection_v2/configs/mini_keystone.yaml` — 24 trials, verification only
- `data_collection_v2/configs/keystone_a.yaml` — **500** trials, seeds 1–500, runs on Machine A (slower)
- `data_collection_v2/configs/keystone_b.yaml` — **1000** trials, seeds 501–1500, runs on Machine B (≈ 2× faster)

Split is 1:2 (A:B) to match expected throughput ratio so both finish in ~12 h. Adjust if real throughput differs (see Phase 2 notes).

All three use the post-yaw-sweep DR envelope: yaw=π±0.5, board x∈[0.13,0.18], y∈[-0.22,-0.18], z∈[1.12,1.16], full physical rail ranges, doc-spec grasp noise.

---

## Phase 0 — preflight (each machine, once)

```bash
# Ensure the aic_eval container exists and is running on each machine.
export DBX_CONTAINER_MANAGER=docker
docker ps --filter name=aic_eval --format '{{.Names}} {{.Status}}'
# If not running:
# docker start aic_eval

# Kill any stale aic_model / recorder / zenoh in the container before launching.
docker exec aic_eval bash -lc 'pkill -KILL -f "aic_model|recorder_node|rmw_zenohd|gz_server|aic_engine" 2>&1 | head; sleep 1; pgrep -af "aic_model|recorder_node|rmw_zenohd" || echo clean'

# Ensure pixi is on PATH
export PATH="$HOME/.pixi/bin:$PATH"
pixi --version   # should be 0.67.2

# Ensure output disk has ≥ 30 GB free (each half writes ~15 GB).
mkdir -p /data/aic_v2
df -h /data/aic_v2
```

---

## Phase 1 — mini-keystone (≈ 30 min, run on whichever machine is faster)

Verify the DR envelope produces leaderboard-grade demos before committing 17+ h.

**Important:** the current `mini_keystone.yaml` uses **halved DR** (nic_yaw ±0.08, grasp_rpy 0.02, board_yaw π±0.3) — a change from the original doc-spec ranges based on the 2026-05-14 wide-DR run (mean total 62.93). The halved-DR variant needs an A/B verification before launching the 12 h keystone. See [`06_dr_verification.md`](./06_dr_verification.md) for:
- the v1 (wide DR) baseline numbers,
- the v2 (halved DR) template to fill in after this run,
- the comparison criteria + decision tree,
- and **explicit copy-paste commands to run this phase on Laptop 2** (faster machine) instead of the desktop.

```bash
cd ~/ws_aic/src/intrinsic-aic-team-autoencoder
pixi run python -m data_collection_v2.cli session \
    --config data_collection_v2/configs/mini_keystone.yaml \
    --output /tmp/aic_v2_mini_keystone
```

Pass criteria (inspect `/tmp/aic_v2_mini_keystone/manifest.jsonl`):
- `valid=true` on ≥ 22 of 24 trials
- Mean `scoring.total` ≥ 75
- Mean `scoring.tier_3_score` ≥ 55 (some trials in the π-yaw band will score ~25)

Quick check:
```bash
python3 -c "
import json
rows = [json.loads(l) for l in open('/tmp/aic_v2_mini_keystone/manifest.jsonl') if l.strip()]
totals = [r['scoring']['total'] for r in rows if r.get('scoring')]
valid = sum(1 for r in rows if r['valid'])
print(f'trials={len(rows)} valid={valid} mean_total={sum(totals)/len(totals):.1f} '
      f'min={min(totals):.1f} max={max(totals):.1f}')
"
```

If pass → Phase 2. If fail → don't launch the full keystone; investigate the failing trials first.

---

## Phase 2 — parallel keystone (run BOTH machines simultaneously)

### Machine A (this computer)

```bash
cd ~/ws_aic/src/intrinsic-aic-team-autoencoder
export PATH="$HOME/.pixi/bin:$PATH" DBX_CONTAINER_MANAGER=docker

nohup pixi run python -m data_collection_v2.cli session \
    --config data_collection_v2/configs/keystone_a.yaml \
    --output /data/aic_v2/keystone_a \
    > /data/aic_v2/keystone_a.host.log 2>&1 &
echo "keystone_a PID=$!"
disown
```

### Machine B (the other laptop)

First, sync the repo (one time):

```bash
# On Machine A:
rsync -avh --exclude='.pixi' --exclude='__pycache__' --exclude='/tmp' \
    --exclude='/data' --exclude='*.pyc' \
    ~/ws_aic/src/intrinsic-aic-team-autoencoder/ \
    <user>@<machine-b>:~/ws_aic/src/intrinsic-aic-team-autoencoder/
```

Then on Machine B:

```bash
cd ~/ws_aic/src/intrinsic-aic-team-autoencoder
export PATH="$HOME/.pixi/bin:$PATH" DBX_CONTAINER_MANAGER=docker

# One-time pixi env install (slow, ~10 min first run)
pixi install

# Bring up aic_eval the same way docs/getting_started.md describes (docker run + entrypoint).
# Verify with: docker exec aic_eval ros2 topic list

nohup pixi run python -m data_collection_v2.cli session \
    --config data_collection_v2/configs/keystone_b.yaml \
    --output /data/aic_v2/keystone_b \
    > /data/aic_v2/keystone_b.host.log 2>&1 &
echo "keystone_b PID=$!"
disown
```

Monitor either machine with:
```bash
tail -f /data/aic_v2/keystone_a.host.log   # or keystone_b.host.log
# or
wc -l /data/aic_v2/keystone_a/manifest.jsonl
```

**Expected wall time** (with 1:2 split):
- Machine A: 500 trials / ~42 ep/h ≈ **12 h**
- Machine B: 1000 trials / ~85 ep/h ≈ **12 h**

If B's measured throughput differs from the 2× assumption, **re-balance after the first hour** by editing `target_total_episodes` in both configs (resume continues from existing manifest, so reducing the target stops collection early; increasing it adds more seeds at the end of the existing range). Easier: monitor `manifest.jsonl` rate at the 1-h mark on both machines and decide whether to leave it, or to give one machine extra trials via a `keystone_c.yaml` with seeds 1501+.

---

## Phase 3 — transfer B's data to A via USB disk

No SSH / network sync needed. Use any USB 3.0 stick or external SSD with ≥ 32 GB free. We use `rsync` *locally* on the USB mount so re-transfers are incremental.

**On Machine B** (after B has been collecting for some hours):

```bash
# Plug in USB, identify the mount path (usually /media/<you>/<label>)
ls /media/$USER/
USB=/media/$USER/<your-usb-label>   # edit me
mkdir -p "$USB/keystone_b"

# Incremental copy — only new/changed files transfer.
rsync -avh --info=progress2 /data/aic_v2/keystone_b/ "$USB/keystone_b/"
sync   # flush kernel buffers before unplug
```

Safely unplug:
```bash
udisksctl unmount -b $(findmnt -no SOURCE "$USB")
```

**On Machine A** (plug the USB in):

```bash
USB=/media/$USER/<your-usb-label>   # same label

# Pull B's data onto A's local disk.
mkdir -p /data/aic_v2/keystone_b
rsync -avh --info=progress2 "$USB/keystone_b/" /data/aic_v2/keystone_b/
sync
```

**Repeat this every few hours.** `rsync` only transfers files that changed since last copy, so after the first full ~10 GB transfer subsequent rounds are fast (just the new parquets). Final transfer at end of B's run grabs the leftover episodes plus the session-end `manifest.jsonl` and `scoring.yaml`.

USB sizing:
- After 4 hours of B running: ~5 GB
- After 12 hours (B's full 1000 trials): ~17 GB
- 32 GB stick has comfortable headroom.

---

## Phase 4 — train while collecting (yes, you can)

**Short answer: yes**, training and collection can overlap on the same machine — but with a real GPU-contention cost on both. Recommended pattern below.

### Why this works (and what it costs)
Machine A's RTX 2000 Ada 16 GB hosts:
- aic_eval container (Gazebo + 3 cameras): ~3 GB VRAM, mostly GPU-compute-bound
- aic_model + recorder: ~2 GB VRAM
- Training (Diffusion Policy or ACT at batch 64, 256×256): ~7 GB VRAM
- Total ≈ 12 GB — fits in 16 GB, no OOM risk.

The cost is **compute time-sharing**, not memory. Empirically expect ~25 % throughput loss on both sides:
- A's collection drops from ~42 → ~30 ep/h
- Training step time goes up by ~25 %

This is acceptable. The alternative (sequential: collect → train) wastes 12 h of A's GPU sitting idle.

### Recommended timeline

| Hour | Machine A | Machine B |
|---|---|---|
| 0–6 | **Collect only** (full speed) | Collect only (full speed) |
| 6 | **USB transfer B → A** (Phase 3), gives A ~300 episodes total | (continues collecting) |
| 6–end | **Collect + train concurrently** on snapshotted ~300 ep | Collect only |
| 12 | USB transfer again, training snapshot grows | (finishing up) |
| 12–end | Continue training on full ~1500 ep snapshot | Done |

Why wait 6 h before starting training: under ~200 episodes, the data is too sparse for a Diffusion Policy / ACT prototype to learn anything useful. 300+ episodes is the realistic floor.

### How to snapshot for training (collection keeps writing to the original path)

LeRobot v2 datasets need three meta files (`info.json`, `episodes.jsonl`, `stats.json`) generated from whatever parquets exist. Collection only writes these at session end, so for a mid-run snapshot we run them manually on a *copy*:

```bash
# Pick a snapshot path.
SNAPSHOT=/data/aic_v2/training_snap_$(date +%Y%m%d_%H%M)
mkdir -p "$SNAPSHOT"

# Copy parquets + manifest from A's live collection AND B's last-synced data.
rsync -a /data/aic_v2/keystone_a/ "$SNAPSHOT"/keystone_a/
rsync -a /data/aic_v2/keystone_b/ "$SNAPSHOT"/keystone_b/   # only what's been USB-transferred so far

# Regenerate meta on each (writes meta/info.json, meta/episodes.jsonl, meta/stats.json).
pixi run python -m data_collection_v2.cli report --output "$SNAPSHOT/keystone_a"
pixi run python -m data_collection_v2.cli report --output "$SNAPSHOT/keystone_b"

# Episode count available for training:
ls "$SNAPSHOT/keystone_a/lerobot_v2/data/chunk-000/" "$SNAPSHOT/keystone_b/lerobot_v2/data/chunk-000/" 2>/dev/null | wc -l
```

Now point your training loader (LeRobot `LeRobotDataset`) at `$SNAPSHOT/keystone_a/lerobot_v2/` (or set up multi-dataset loading across both). Collection keeps appending to `/data/aic_v2/keystone_a/`; your snapshot is frozen at this moment.

### A subtlety: scoring isn't backfilled mid-run

The manifest's `scoring` field is `null` until the engine writes `engine_results/scoring.yaml` at session end. **Mid-run snapshots have unscored manifests.** That means:
- You can train on the parquets just fine (the demo data is complete).
- You can NOT do the "filter `total ≥ 70`" trick from Phase 5 — there's nothing to filter on yet.
- First training pass therefore trains on **all** mid-run demos including the low-quality yaw=π ones. That's OK for a prototype; the production model trains on the filtered final dataset.

If you need scoring early, run `pixi run python -m data_collection_v2.cli report --output /data/aic_v2/keystone_a` *on the live collection dir* — it reads whatever `scoring.yaml` is there. The engine doesn't write `scoring.yaml` until session end, so this will only help once A's collection completes.

### Don't try to train on B

B has no `pixi` env, no model weights, possibly different CUDA. Keep B as collection-only. All training happens on A.

---

## Phase 5 — filter for quality before final training

Once collection is done, build the filtered training set:

```bash
python3 <<'EOF'
import json, shutil
from pathlib import Path

src_a = Path('/data/aic_v2/keystone_a')
src_b = Path('/data/aic_v2/keystone_b')
dst   = Path('/data/aic_v2/keystone_filtered')

THRESHOLD = 70.0   # drop trials below this total score (mostly the yaw=π band)

rows = []
for src in (src_a, src_b):
    for line in (src / 'manifest.jsonl').read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get('valid') and (r.get('scoring') or {}).get('total', 0) >= THRESHOLD:
            r['_src'] = str(src)
            rows.append(r)
print(f'kept {len(rows)} of input trials (threshold total >= {THRESHOLD})')
# NB: writing the merged lerobot_v2 dataset (renumbered episode_index, fresh
# meta/info.json + episodes.jsonl + stats.json) is a separate step — see
# data_collection_v2/pipeline/lerobot_v2_writer.py for the schema.
EOF
```

A proper merge utility (rebuilds meta files + renumbers episodes) is **not yet written**. When you reach Phase 5, ask and we'll add it — needs careful handling of stats.json regeneration.

---

## Notes

- **Per-machine seed ranges are disjoint** (1–750 on A, 751–1500 on B), so even though both write to local paths there are no manifest collisions when merged.
- The `nohup ... &` + `disown` pattern survives terminal disconnect. To stop a run: `pkill -f "data_collection_v2.cli session"` followed by the container hygiene step from Phase 0.
- If a run dies mid-session, **resume** it with: `pixi run python -m data_collection_v2.cli resume --config <yaml> --output <same-output-dir>`. The manifest's completed seeds are skipped automatically.
- Eval cloud is L4 24 GB sm_89; Desktop is RTX 2000 Ada 16 GB sm_89 — same compute capability, so training that fits on Desktop will fit on eval.
