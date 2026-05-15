# DR-envelope verification — comparing wide vs halved domain randomization

We need to pick the DR envelope that produces the **highest-quality demos** for FastCheatCode before launching the 1500-trial keystone. CheatCode is open-loop and fragile, so wider DR ⇒ more failed trials.

This file captures:
- v1 result (wide DR, what `keystone_1500.yaml` used to have)
- v2 result template (halved DR, **TO BE FILLED IN**)
- The exact metrics to compare
- Commands to run v2 on the **faster laptop** while this machine stays idle (or does something else)

Reads upstream: [`05_keystone_playbook.md`](./05_keystone_playbook.md), [`context/04_training/05_keystone_dataset.md`](../04_training/05_keystone_dataset.md).

---

## What the two runs differ on

Both runs use 24 trials, identical seed range (1–24), identical FastCheatCode policy, identical board x/y/z ranges and nic_rail_translation_range. **Only these axes differ:**

| Axis | v1 (wide) | v2 (halved) |
| --- | --- | --- |
| `nic_card_yaw_offset_range_rad` | ±0.17 (doc-spec) | ±0.08 |
| `grasp_offset_rpy_sigma_rad` | 0.04 (doc-spec) | 0.02 |
| `task_board_yaw_range` | [2.64, 3.64] (π±0.5) | [2.84, 3.44] (π±0.3) |

Everything else (nic_rail ±0.022, sc_rail [-0.06,+0.055], grasp_xyz σ=0.002, board x/y/z) is identical.

---

## v1 — wide DR (2026-05-14, mini-keystone @ `/tmp/aic_v2_mini_keystone_widedr_1945`)

```
24 trials, 24 valid (100% conformance)

Mean total:    62.93     (top-30 floor per trial ≈ 58.7)
Min / Max:     15.52 / 96.49
Mean tier_2:   16.57     (top teams ~21)
Mean tier_3:   45.36     (cap = 75)
tier_3 = 75:   5 / 24    (full-insertion rate ≈ 21%)

Filter survival rates:
  total ≥ 85:   5 / 24  (21%)   ← high-quality bucket for training
  total ≥ 70:   8 / 24  (33%)   ← "keep filter" bucket
  total ≥ 50:  17 / 24  (71%)

Per-target breakdown:
  sfp nic0:  n=2  mean=73.1   1 success
  sfp nic1:  n=2  mean=50.3   0 successes
  sfp nic2:  n=6  mean=71.9   3 successes   ★ best NIC
  sfp nic3:  n=4  mean=49.2   0 successes   ⚠ worst NIC
  sfp nic4:  n=1  mean=56.0   0 successes
  sc sc_port_0: n=5  mean=68.9   1 success
  sc sc_port_1: n=4  mean=58.7   0 successes
```

Notable: **nic3 had 0 full successes across 4 trials**. This matched the coverage test (zero-DR nic3 sfp_port_0 scored -11, sfp_port_1 scored 96 — nic3 sfp_port_0 specifically is structurally hard).

Forecast at this rate over 1500 trials: ~315 demos clear the 85-filter, ~495 clear the 70-filter. Trained policy lands at ~top-30 boundary per IL gap estimate.

---

## v2 — halved DR (TO RUN; result template below)

The first v2 attempt on this desktop was corrupted by a rosbag-cleaner bug (`v2_entrypoint.sh` used `find -mmin` on directory mtime which doesn't update during bag growth; live bags got deleted, tier_2 collapsed to 4.17). The cleaner is now fixed (keeps the 2 newest bag dirs by `ls -1dt` order). **Re-run on the faster laptop.**

After the run completes on Laptop 2, **fill the table below** with the same metrics from v1 so we can A/B compare:

```
24 trials, ___ valid

Mean total:    ___       (compare to v1's 62.93)
Min / Max:     ___ / ___
Mean tier_2:   ___       (compare to v1's 16.57)
Mean tier_3:   ___       (compare to v1's 45.36)
tier_3 = 75:   __ / 24   (compare to v1's 5)

Filter survival rates:
  total ≥ 85:  __ / 24  (___%)
  total ≥ 70:  __ / 24  (___%)
  total ≥ 50:  __ / 24  (___%)

Per-target breakdown (focus on whether nic3 recovers):
  sfp nic0:  n=__  mean=___   _ successes
  sfp nic1:  n=__  mean=___   _ successes
  sfp nic2:  n=__  mean=___   _ successes
  sfp nic3:  n=__  mean=___   _ successes   (was 0 in v1)
  sfp nic4:  n=__  mean=___   _ successes
  sc sc_port_0: n=__  mean=___   _ successes
  sc sc_port_1: n=__  mean=___   _ successes

Throughput: __ ep/h   (compare to v1's ~37 ep/h)
```

---

## How to decide — what to compare and the thresholds

Look at four numbers, in priority order. Decide based on the joint pattern, not any one alone.

### 1. Filter-at-70 rate — **the headline metric**

This is the fraction of trials that survive into the training set. Higher means more demos for less wall time.

- v1: 33 %
- **Decide v2 wins if:** ≥ 50 % (1500 trials → 750 demos, comfortable for Diffusion Policy)
- **Decide v1 wins if:** v2 < 35 % (the narrower DR didn't help and we lost coverage breadth)

### 2. Mean total — **demo quality**

The IL student-teacher gap means policy ≈ (data mean) × 0.75–0.85. To beat top-30 (176/3 = 58.7 per trial), demos must average ≥ 70.

- v1: 62.93 (marginal)
- **Decide v2 wins if:** ≥ 75
- **Concerning if v2 < v1:** narrowing DR shouldn't *hurt* mean — if it does, something else changed (rosbag cleaner regression, seed-RNG drift, etc.) — investigate before launching keystone

### 3. Per-NIC distribution — **structural failure check**

The wide-DR run had nic3 = 0 full successes across 4 trials. We want to know if that's:
- A nic3 structural issue (still fails at v2)
- A DR-amplification effect (recovers at v2)

- **Decide nic3 is structurally broken if:** v2 nic3 still has 0 successes — flag it and consider excluding nic3 from training, or build a nic3-specific patch to FastCheatCode
- **Decide DR was the cause if:** v2 nic3 has ≥ 1 success at mean ≥ 60 — proceed with keystone, nic3 will appear at normal rates

### 4. Throughput — **time budget sanity**

If trials take longer (more hit the 40 s sim cap), wall time per trial grows.

- v1: ~37 ep/h
- **Concerning if v2 < 35 ep/h:** keystone will overrun the 12 h target. Acceptable if mean total improves enough to justify.
- **Expected if v2 wins on quality:** ~40 ep/h (fewer trials hit the time cap because they insert successfully earlier).

### Decision tree

```
v2 filter-at-70 ≥ 50% AND mean total ≥ 75
    └─► launch keystone with halved DR (configs already point to it)

v2 filter-at-70 in [35%, 50%) AND mean total in [65, 75)
    └─► launch keystone with halved DR but EXPECT top-25 to -30 only
        (no margin for the IL gap)

v2 filter-at-70 < 35% OR mean total < v1 mean
    └─► STOP. Re-investigate. Likely cleaner or another regression.
        Don't burn 12 h on keystone until the regression is found.

v2 wins overall BUT nic3 still has 0 successes
    └─► launch keystone with halved DR, but bias nic3 out of training:
        in the filtered loader, drop or down-weight nic3 rows.
        Eval doesn't have to test nic3 specifically; nic2/0/1 dominate.
```

---

## Running v2 on Laptop 2 (the faster machine)

This assumes Laptop 2 already has the repo cloned and pixi installed (per `docs/getting_started.md`). If not, do that first.

### Sync the latest changes to Laptop 2 (via USB or git)

The DR changes + cleaner fix are in three files on this machine. On Laptop 2, get them from git (preferred) or USB.

**Option A — git (if repo is committed and pushed somewhere accessible):**
```bash
cd ~/ws_aic/src/intrinsic-aic-team-autoencoder
git pull
```

**Option B — USB sync (if no git remote between machines):**
On this machine:
```bash
USB=/media/$USER/<your-usb-label>
rsync -avh --delete \
    --include='data_collection_v2/' \
    --include='data_collection_v2/**' \
    --include='context/' \
    --include='context/**' \
    --include='CLAUDE.md' --include='AGENTS.md' \
    --exclude='*' \
    ~/ws_aic/src/intrinsic-aic-team-autoencoder/ \
    "$USB/aic_sync/"
sync
```

Plug into Laptop 2:
```bash
USB=/media/$USER/<your-usb-label>
rsync -avh "$USB/aic_sync/" ~/ws_aic/src/intrinsic-aic-team-autoencoder/
```

The critical files to land on Laptop 2:
- `data_collection_v2/configs/mini_keystone.yaml` (halved DR)
- `data_collection_v2/container/v2_entrypoint.sh` (fixed cleaner)
- `data_collection_v2/policy/FastCheatCode.py`
- `data_collection_v2/pipeline/coverage.py`

### Pre-flight on Laptop 2

```bash
export DBX_CONTAINER_MANAGER=docker
export PATH="$HOME/.pixi/bin:$PATH"

# 1. aic_eval container running?
docker ps --filter name=aic_eval --format '{{.Names}} {{.Status}}'
#   If not: docker start aic_eval

# 2. Kill any stale ROS processes from a prior run.
docker exec aic_eval bash -lc 'pkill -KILL -f "aic_model|recorder_node|rmw_zenohd|gz_server|aic_engine" 2>&1 | head; sleep 1; pgrep -af "aic_model|recorder_node|rmw_zenohd" || echo clean'

# 3. Confirm port 7447 is free.
docker exec aic_eval ss -ltn 2>&1 | grep 7447 || echo "port 7447 free"

# 4. Confirm disk has room (mini-keystone needs ~5 GB).
df -h /tmp | head -2

# 5. Sanity-import the policy + cleaner.
cd ~/ws_aic/src/intrinsic-aic-team-autoencoder
pixi run python -c "from data_collection_v2.policy.FastCheatCode import FastCheatCode; print('OK', FastCheatCode.__module__)"
bash -n data_collection_v2/container/v2_entrypoint.sh && echo "OK entrypoint syntax"
```

### Run mini-keystone v2 on Laptop 2

```bash
cd ~/ws_aic/src/intrinsic-aic-team-autoencoder
export PATH="$HOME/.pixi/bin:$PATH" DBX_CONTAINER_MANAGER=docker

# Move aside any prior result.
[ -d /tmp/aic_v2_mini_keystone ] && mv /tmp/aic_v2_mini_keystone /tmp/aic_v2_mini_keystone_prev_$(date +%H%M%S) || true

# Launch (foreground; ~20-25 min on a fast laptop).
pixi run python -m data_collection_v2.cli session \
    --config data_collection_v2/configs/mini_keystone.yaml \
    --output /tmp/aic_v2_mini_keystone
```

### Extract the metrics on Laptop 2 and paste them into v2's template above

```bash
python3 - <<'EOF'
import json, collections
rows = [json.loads(l) for l in open('/tmp/aic_v2_mini_keystone/manifest.jsonl') if l.strip()]
valid = [r for r in rows if r.get('valid') and r.get('scoring')]
totals = [r['scoring']['total'] for r in valid]
t2 = [r['scoring']['tier_2_score'] for r in valid]
t3 = [r['scoring']['tier_3_score'] for r in valid]
print(f'valid: {len(valid)} / {len(rows)}')
print(f'mean total: {sum(totals)/len(totals):.2f}  min: {min(totals):.2f}  max: {max(totals):.2f}')
print(f'mean tier_2: {sum(t2)/len(t2):.2f}  mean tier_3: {sum(t3)/len(t3):.2f}')
print(f'tier_3=75 count: {sum(1 for t in t3 if t>=74.5)} / {len(t3)}')
print(f'>=85: {sum(1 for t in totals if t>=85)}/{len(totals)}  '
      f'>=70: {sum(1 for t in totals if t>=70)}/{len(totals)}  '
      f'>=50: {sum(1 for t in totals if t>=50)}/{len(totals)}')
buckets = collections.defaultdict(list)
for r in valid:
    tc = r['trial_config']
    k = f'sfp nic{tc["nic_card_index"]}' if tc['plug_type']=='sfp' else f'sc {tc["target_module_name"]}'
    buckets[k].append(r['scoring']['total'])
for k in sorted(buckets):
    scs = buckets[k]
    print(f'  {k}: n={len(scs)} mean={sum(scs)/len(scs):.1f} successes(>=85)={sum(1 for s in scs if s>=85)}')
EOF
```

Bring the numbers back to this machine (USB or text paste) and update v2's section above. Then apply the decision tree.

---

## What this machine (desktop) does while Laptop 2 runs v2

Nothing data-collection-related — both machines collecting the same DR would be redundant for *verification*. Options for the desktop:

1. **Idle / pause** (simplest; ~25 min of nothing).
2. **Start sketching the filter+merge utility** (`data_collection_v2/scripts/build_filtered_dataset.py`) that we'll need before training — see [`context/04_training/05_keystone_dataset.md`](../04_training/05_keystone_dataset.md) § "Building a merged LeRobot dataset". Ask Claude to do it.
3. **Inspect a tier-3=25 trial's parquet to ground-truth the failure-mode hypothesis** (cable bounces off port).

(2) is the highest-leverage use of the 25 min. (3) is informational only.
