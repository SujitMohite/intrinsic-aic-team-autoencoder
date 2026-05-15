# Data collection status — 2026-05-15

## What we have now

### keystone_a (this laptop, T1000 4 GB)

- **Path**: `~/aic_data/keystone_a/`
- **Config**: `data_collection_v2/configs/keystone_a.yaml` (seeds 1–500, halved DR)
- **Status**: 269 / 500 trials completed, still running (PID 157409). ~25 ep/h.
- **Scoring**: `scoring.yaml` not yet written (session still in progress), BUT per-trial scores extracted from session log → `~/aic_data/keystone_a/manifest_scored.jsonl`
- **Score distribution (269 trials)**:
  ```
  mean total: 76.61   min: -35.00   max: 97.02
  >=85:  112/269  (42%)
  >=70:  174/269  (65%)   ← headline filter
  >=50:  252/269  (94%)
  < 0:     4/269  (1%)
  ```
- **Filtered dataset ready**: `~/aic_data/keystone_a_filtered_t70/` — 174 episodes, mean 87.04, 3.6 GB, with full LeRobot v2 meta (info.json, episodes.jsonl, tasks.jsonl, stats.json). USB-copy to Laptop 2 for training.

### keystone_b (Laptop 2, RTX 4070 8 GB)

- **Path**: `~/aic_data/keystone_b/` (on Laptop 2)
- **Config**: `data_collection_v2/configs/keystone_b.yaml` (seeds 501–1500)
- **Status**: Gazebo crashed mid-run. Parquets on disk survive; scoring.yaml lost. Unrecoverable scoring for the completed trials (engine didn't write it before crash).
- **Recovery**: per-trial scores CAN be extracted from the session log if it still exists: `grep "Finished scoring trial" ~/aic_data/keystone_b/logs/session_*.log | awk -F'is: ' '{print $2}' | wc -l`
- **If session log is intact**: run the same extraction script used on keystone_a (see § "How to extract scores from session log" below).

---

## New strategy: 25-episode chunk collection (crash-resilient)

### Why

The single-session approach (500–1000 trials) only writes `scoring.yaml` at session end. If Gazebo crashes mid-session, all per-trial scoring is lost. The parquets survive, but without scoring we can't filter for quality.

### How

Run 25 trials per session. Each 25-trial session finishes cleanly → engine writes `scoring.yaml` → `_backfill_scoring` merges scores into `manifest.jsonl`. Then the next session `resume`s from where the manifest left off. Automated by `run_chunked.sh`.

### Configs

| Config | Seeds | Use on |
| --- | --- | --- |
| `data_collection_v2/configs/keystone_chunk25.yaml` | `seed_start: 1` | Machine A (this laptop) |
| `data_collection_v2/configs/keystone_chunk25_b.yaml` | `seed_start: 501` | Machine B (Laptop 2) |

Both use the halved-DR envelope (nic_yaw ±0.08, grasp_rpy σ=0.02, board_yaw π±0.3).

### Commands

**Machine A (T1000):**
```bash
# Stop the current single-session keystone_a if still running:
kill 157409   # or: pkill -f "data_collection_v2.cli session"

cd ~/ws_aic/src/intrinsic-aic-team-autoencoder
nohup bash data_collection_v2/scripts/run_chunked.sh 500 ~/aic_data/keystone_chunk_a \
    > ~/aic_data/keystone_chunk_a.log 2>&1 &
disown
```

**Machine B (Laptop 2 / RTX 4070):**
```bash
# Kill any stale processes from the crashed run first:
docker exec aic_eval bash -lc 'pkill -KILL -f "aic_model|recorder_node|rmw_zenohd|gz_server|aic_engine" 2>/dev/null; sleep 2; true'

cd ~/ws_aic/src/intrinsic-aic-team-autoencoder
nohup bash data_collection_v2/scripts/run_chunked.sh 1000 ~/aic_data/keystone_chunk_b \
    > ~/aic_data/keystone_chunk_b.log 2>&1 &
disown
```

**Monitor either machine:**
```bash
tail -f ~/aic_data/keystone_chunk_a.log   # or keystone_chunk_b.log
wc -l ~/aic_data/keystone_chunk_a/manifest.jsonl
```

### run_chunked.sh behavior

- Runs `pixi run python -m data_collection_v2.cli session` with the 25-trial config
- After each 25-trial chunk: scores are backfilled into manifest, then loop restarts
- On Gazebo crash (exit code ≠ 0): kills stale processes, waits 5 s, retries. At most 25 trials lose scoring per crash.
- The `session` CLI with the same `--output` dir reads existing `manifest.jsonl` and skips completed seeds (resume built-in).
- Stops when manifest has `TARGET_TOTAL` rows.

**Note for Machine B**: `run_chunked.sh` defaults to the `keystone_chunk25.yaml` config (seed_start: 1). For Machine B, edit line 19 of `run_chunked.sh` or pass the config explicitly:
```bash
CONFIG=data_collection_v2/configs/keystone_chunk25_b.yaml \
    bash data_collection_v2/scripts/run_chunked.sh 1000 ~/aic_data/keystone_chunk_b
```

Actually, the cleanest way: edit `run_chunked.sh` line 19 to accept `CONFIG` from env:
```bash
CONFIG="${AIC_V2_CHUNK_CONFIG:-data_collection_v2/configs/keystone_chunk25.yaml}"
```
This is already in the script — set the env var to use the B config.

---

## How to extract scores from session log (for any crashed/in-progress run)

If `scoring.yaml` was never written but the session log exists, per-trial scores can be recovered:

```bash
# 1. Find the session log
SESS=$(ls -t ~/aic_data/<run_dir>/logs/session_*.log | head -1)

# 2. Count scored trials
grep -c "Finished scoring trial" "$SESS"

# 3. Extract scores + compute stats
python3 <<'EOF'
import re, json
sess = "<paste session log path>"
manifest = "<paste manifest.jsonl path>"

trial_scores = {}
with open(sess) as f:
    for line in f:
        m = re.search(r"Finished scoring trial, total score is: ([-\d.]+)", line)
        if m:
            trial_scores[len(trial_scores)+1] = float(m.group(1))

print(f"extracted {len(trial_scores)} trial scores")
scores = list(trial_scores.values())
if scores:
    print(f"mean: {sum(scores)/len(scores):.2f}  min: {min(scores):.2f}  max: {max(scores):.2f}")
    print(f">=85: {sum(1 for s in scores if s>=85)}/{len(scores)}")
    print(f">=70: {sum(1 for s in scores if s>=70)}/{len(scores)}")

# Write scored manifest
rows = [json.loads(l) for l in open(manifest) if l.strip()]
for i, row in enumerate(rows):
    t = i + 1
    if t in trial_scores:
        if row.get("scoring") is None:
            row["scoring"] = {}
        row["scoring"]["total"] = trial_scores[t]
        row["valid"] = True

scored_path = manifest.replace("manifest.jsonl", "manifest_scored.jsonl")
with open(scored_path, "w") as f:
    for row in rows:
        f.write(json.dumps(row) + "\n")
print(f"wrote {scored_path}")
EOF
```

---

## How to build a filtered dataset from scored manifest

Once you have `manifest_scored.jsonl` (either from a clean run or from the extraction above):

```bash
python3 <<'EOF'
import json, shutil
from pathlib import Path

SRC = Path("~/aic_data/<run_dir>").expanduser()     # where the raw parquets live
DST = Path("~/aic_data/<run_dir>_filtered_t70").expanduser()
THRESHOLD = 70.0

scored = SRC / "manifest_scored.jsonl"
rows = [json.loads(l) for l in scored.read_text().splitlines() if l.strip()]
kept = [r for r in rows if r.get("scoring", {}).get("total", -999) >= THRESHOLD]
print(f"kept {len(kept)} / {len(rows)} episodes at threshold {THRESHOLD}")

dst_data = DST / "lerobot_v2" / "data" / "chunk-000"
dst_data.mkdir(parents=True, exist_ok=True)
(DST / "lerobot_v2" / "meta").mkdir(parents=True, exist_ok=True)

new_manifest = []
for new_idx, row in enumerate(kept):
    old_pq = SRC / "lerobot_v2" / row["parquet_path"]
    new_name = f"episode_{new_idx:06d}.parquet"
    if old_pq.exists():
        shutil.copy2(old_pq, dst_data / new_name)
    row["episode_index"] = new_idx
    row["parquet_path"] = f"data/chunk-000/{new_name}"
    new_manifest.append(row)

(DST / "manifest_scored.jsonl").write_text("\n".join(json.dumps(r) for r in new_manifest) + "\n")

# Meta files
import json as _json
with (DST / "lerobot_v2" / "meta" / "episodes.jsonl").open("w") as f:
    for r in new_manifest:
        f.write(_json.dumps({"episode_index": r["episode_index"], "task": r.get("task","sfp_insertion"), "length": r.get("n_rows",400)}) + "\n")

tasks = sorted(set(r.get("task","sfp_insertion") for r in new_manifest))
with (DST / "lerobot_v2" / "meta" / "tasks.jsonl").open("w") as f:
    for i, t in enumerate(tasks):
        f.write(_json.dumps({"task_index": i, "task": t}) + "\n")

info = {"fps": 20, "total_episodes": len(new_manifest),
        "total_frames": sum(r.get("n_rows",400) for r in new_manifest),
        "camera_hw": [256, 256], "camera_names": ["left", "center", "right"]}
(DST / "lerobot_v2" / "meta" / "info.json").write_text(_json.dumps(info, indent=2))

print(f"filtered dataset: {DST}")
print(f"  {len(new_manifest)} episodes, mean score {sum(r['scoring']['total'] for r in new_manifest)/len(new_manifest):.2f}")
EOF
```

After building the filtered dataset, generate `stats.json` (normalization):

```bash
pixi run python3 <<'EOF'
import numpy as np, pyarrow.parquet as pq, json
from pathlib import Path

DST = Path("~/aic_data/<run_dir>_filtered_t70/lerobot_v2").expanduser()
parquets = sorted(DST.glob("data/chunk-000/episode_*.parquet"))
accum = {}
for pq_path in parquets:
    df = pq.read_table(pq_path).to_pandas()
    for col in ["observation.state", "observation.wrench", "action"]:
        arr = np.stack(df[col].to_numpy())
        if col not in accum:
            accum[col] = {"sum": np.zeros(arr.shape[1]), "sum2": np.zeros(arr.shape[1]),
                          "min": np.full(arr.shape[1], np.inf), "max": np.full(arr.shape[1], -np.inf), "n": 0}
        accum[col]["sum"] += arr.sum(axis=0)
        accum[col]["sum2"] += (arr**2).sum(axis=0)
        accum[col]["min"] = np.minimum(accum[col]["min"], arr.min(axis=0))
        accum[col]["max"] = np.maximum(accum[col]["max"], arr.max(axis=0))
        accum[col]["n"] += len(arr)

stats = {}
for col, a in accum.items():
    mean = a["sum"] / a["n"]
    std = np.sqrt(np.maximum(a["sum2"] / a["n"] - mean**2, 0))
    std = np.maximum(std, 1e-6)
    stats[col] = {"mean": mean.tolist(), "std": std.tolist(), "min": a["min"].tolist(), "max": a["max"].tolist()}

(DST / "meta" / "stats.json").write_text(json.dumps(stats, indent=2))
print(f"wrote stats.json over {len(parquets)} episodes")
EOF
```

---

## USB transfer plan

### To start training on Laptop 2

1. **Plug USB into this laptop (T1000).**
2. Copy filtered dataset:
   ```bash
   USB=/media/$USER/<label>
   rsync -avh --info=progress2 ~/aic_data/keystone_a_filtered_t70/ "$USB/keystone_a_filtered_t70/"
   sync
   ```
3. **Also copy the repo** (so Laptop 2 has the latest configs + scripts):
   ```bash
   rsync -avh --delete \
       --exclude='.pixi' --exclude='__pycache__' --exclude='*.pyc' \
       --exclude='/data' --exclude='/tmp' \
       ~/ws_aic/src/intrinsic-aic-team-autoencoder/ \
       "$USB/aic_sync/"
   sync
   ```
4. **Unplug, plug into Laptop 2.**
5. On Laptop 2:
   ```bash
   USB=/media/$USER/<label>
   # Sync repo
   rsync -avh "$USB/aic_sync/" ~/ws_aic/src/intrinsic-aic-team-autoencoder/
   # Copy training data
   rsync -avh "$USB/keystone_a_filtered_t70/" ~/aic_data/keystone_a_filtered_t70/
   ```
6. Laptop 2 now has 174 filtered episodes ready for training at `~/aic_data/keystone_a_filtered_t70/lerobot_v2/`.

### To sync new chunk data later

Repeat the rsync from either machine's `~/aic_data/keystone_chunk_*` to USB, then to the other machine. `rsync` is incremental — only new parquets transfer.

---

## Key findings from the data collection experiments (2026-05-14 to 2026-05-15)

### FastCheatCode performance

- **FastCheatCode** (`data_collection_v2/policy/FastCheatCode.py`) is a TF-based early-exit fork of upstream CheatCode. It exits the descent loop when either the `/scoring/insertion_event` topic fires OR the plug tip TF check detects co-location with the port.
- It cut per-trial wall time by ~50% vs upstream CheatCode (100 s vs 191 s), verified on the 3-trial smoke (all scored 95+).
- It is **open-loop** — no force feedback, no contact-driven micro-correction. This means it's fragile to wide domain randomization.

### Domain randomization findings

| DR envelope | Mean total | Filter-at-70 | Source |
| --- | --- | --- | --- |
| **Smoke (narrow)** | 96.1 | ~100% | 3-trial smoke, NIC 1 only |
| **Wide (doc-spec)** | 62.9 | 33% | 24-trial mini-keystone v1 |
| **Halved** | 79.8 | 58% | 24-trial mini-keystone v2 (Laptop 2) |
| **keystone_a actual (halved, 269 trials)** | 76.6 | 65% | keystone_a on T1000 |

The halved DR envelope is confirmed as the sweet spot: balanced between data quality and DR breadth.

### Board yaw degeneracy

Board yaw exactly at π (180°) causes scoring to drop to ~38 total (5-trial yaw sweep result). Yaw at π±0.25 or π±0.5 scores 96. Current DR uses [2.84, 3.44] (π±0.3). Some trials will land near π and score low — these are filtered out.

### NIC 3 behavior

NIC 3 was structurally broken at wide DR (0/4 successes in mini v1). Recovered at halved DR (2/4 successes in mini v2). Not a hard blocker but worth monitoring.

### Rosbag cleaner

The v2_entrypoint.sh includes a rosbag cleaner (keeps newest 2 bag dirs, deletes older). Initial implementation using `find -mmin` was buggy (deleted live bags based on stale dir mtime). Fixed to use `ls -1dt | tail -n +3 | xargs rm -rf`. Without the cleaner, 500 trials accumulate ~500 GB of bags.

### Hardware throughput

| Machine | GPU | VRAM | Throughput | Training viable? |
| --- | --- | --- | --- | --- |
| Laptop 1 (T1000) | Quadro T1000 Max-Q | 4 GB | ~25-38 ep/h | **No** (only 1.2 GB VRAM free during collection) |
| Laptop 2 (RTX 4070) | RTX 4070 Mobile | 8 GB | ~106 ep/h | **Yes** (bf16 batch 4-8 fits in 5 GB free; train after collection) |

Both are sm_89 (Ada / Turing lineage) — compiled artifacts work on L4 eval cloud (sm_89) without rebuild.

### Scoring recovery

If Gazebo crashes before `scoring.yaml` is written, per-trial scores can be recovered from the session log (`grep "Finished scoring trial"`). The "25-episode chunk" strategy (`run_chunked.sh`) minimizes the blast radius of a crash to 25 trials.
