# Keystone Dataset — what you'll train on

The **keystone dataset** is the team's main FastCheatCode-generated training corpus, collected via `data_collection_v2/`. This file briefs a future training session on where it lives, what's inside, and the **mandatory filter step** before training.

Source: `data_collection_v2/`, [`05_keystone_playbook.md`](../07_team/05_keystone_playbook.md), [`context/10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md).

## Where it lives

Two halves, collected in parallel on two machines:

| Path | Machine | Seeds | Target trials |
| --- | --- | --- | --- |
| `/data/aic_v2/keystone_a/` | Desktop / slower machine | 1–500 | 500 |
| `/data/aic_v2/keystone_b/` | Faster laptop, USB-synced back to A | 501–1500 | 1000 |

After both finish, USB-rsync B → A so the entire dataset is under `/data/aic_v2/` on the training machine.

Both halves share the same LeRobot v2 layout:
```
keystone_{a,b}/
  manifest.jsonl                 one row per episode: trial_config + scoring
  lerobot_v2/
    meta/info.json               fps, total_episodes, camera_hw, camera names
    meta/episodes.jsonl          per-episode metadata for the LeRobot loader
    meta/tasks.jsonl             task index (plug type + port)
    meta/stats.json              feature min/max/mean/std for normalization
    data/chunk-000/
      episode_000000.parquet     ~17 MB each
      episode_000001.parquet
      ...
  engine_results/scoring.yaml    session-end scoring (tier 1/2/3 per trial)
  sessions/, logs/               sweep yaml + container logs (debug only)
```

## Parquet schema (one row = one 50 ms sim step, 20 Hz)

| Column | Type | Notes |
| --- | --- | --- |
| `observation.images.left/center/right` | bytes (JPG, 256×256, q=85) | three wrist cameras |
| `observation.state` | list[float] × 25 | TCP pose 7 + TCP vel 6 + joint pos 6 + joint vel 6 |
| `observation.wrench` | list[float] × 6 | F/T sensor at end-effector (Fx,Fy,Fz,Tx,Ty,Tz) |
| `action` | list[float] × 13 | commanded pose 7 + stiffness 3 + damping 3 |
| `next.reward` | float | 0 except 1 on the frame insertion_event fires |
| `next.success` | bool | True on last frame iff `valid` and `tier_1_score == 1` |
| `next.done` | bool | True only on last frame |
| `timestamp`, `frame_index`, `episode_index`, `task_index`, `index` | various | LeRobot-required |

Per-episode length: typically 300–500 rows (15–25 s of sim).

## Manifest row schema (one JSON object per line)

Each row in `manifest.jsonl` looks like:
```jsonc
{
  "ep_id": "ep_gz_sfp_nic2_s000037",
  "seed": 37,
  "trial_config": {                  // exact randomization for this episode
    "plug_type": "sfp",
    "port_name": "sfp_port_0",
    "target_module_name": "nic_card_mount_2",
    "nic_card_index": 2,
    "nic_rail_translation_m": 0.0123,
    "nic_card_yaw_offset_rad": -0.045,
    "task_board_x": 0.162, "task_board_y": -0.198, "task_board_z": 1.142,
    "task_board_yaw": 3.087,
    "grasp_offset_x": 0.0011, ..., "grasp_offset_yaw": -0.0024,
    "time_limit_s": 40
  },
  "parquet_path": "data/chunk-000/episode_000036.parquet",
  "valid": true,
  "scoring": {
    "tier_1_score": 1, "tier_2_score": 19.84,
    "tier_3_score": 75.0, "tier_3_message": "Cable insertion successful.",
    "total": 95.84
  }
}
```

Use `manifest.jsonl` to filter episodes for training (next section).

## CRITICAL — filter before training

**Do not train on the raw keystone.** FastCheatCode is open-loop (TF-based descent, no force feedback), so ~½–⅔ of raw trials get tier-3 partial credit and would teach the policy bad habits.

The filter is **`total ≥ 70`** (or **`≥ 85`** for higher quality at the cost of fewer episodes):

```python
import json
from pathlib import Path

ROOT = Path("/data/aic_v2")
THRESHOLD = 70   # raise to 85 for top-15 quality, lower to 50 for max episode count

def load_filtered(half: str) -> list[dict]:
    rows = []
    for line in (ROOT / half / "manifest.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("valid") and (r.get("scoring") or {}).get("total", 0) >= THRESHOLD:
            r["_parquet_abspath"] = ROOT / half / "lerobot_v2" / r["parquet_path"]
            rows.append(r)
    return rows

rows = load_filtered("keystone_a") + load_filtered("keystone_b")
print(f"kept {len(rows)} episodes at threshold {THRESHOLD}")
# Pass [r['_parquet_abspath'] for r in rows] to your LeRobot dataset loader,
# or symlink/copy them into a single filtered LeRobot dataset root.
```

Expected episode counts after filtering. Numbers below are **measured from the 2026-05-14 mini-keystone v2** at the halved-DR envelope (24 trials, mean total 79.78, see [`06_dr_verification.md`](../07_team/06_dr_verification.md) for the full breakdown):

| Threshold | v2 measured rate | Forecast at 1500 trials |
|---|---|---|
| `total ≥ 85` | 54 % (13/24) | **~810 episodes** |
| `total ≥ 70` | 58 % (14/24) | **~870 episodes** |
| `total ≥ 50` | 92 % (22/24) | **~1380 episodes** |

The v2 score distribution is **bimodal** — trials either insert cleanly (tier_3=75, total ≥ 85) or fail visibly (total < 50). Only ~4 % of trials live in the 70–85 band, so threshold ≥ 70 and ≥ 85 are nearly equivalent in selectivity but ≥ 70 keeps an extra ~60 demos.

**Default for first pass: `total ≥ 70`.** Diffusion Policy wants ≥ 500 demos; ACT works with 200+. Both clear comfortably at this threshold. Drop to ≥ 50 only if the full keystone underperforms its mini-keystone forecast.

## Building a merged LeRobot dataset from the filtered subset

LeRobot's `LeRobotDataset` needs `meta/info.json`, `meta/episodes.jsonl`, `meta/stats.json`. The keystone halves each have their own; you need a **merged** set for the filtered subset.

A merge utility was deliberately deferred during collection — when you reach this point, ask Claude to write it. The shape is:
1. Renumber `episode_index` consecutively across the filtered subset
2. Copy each filtered parquet to `data/chunk-000/episode_NNNNNN.parquet` with the new index
3. Rebuild `meta/info.json` with the new `total_episodes`
4. Rebuild `meta/episodes.jsonl` (one row per kept episode)
5. Recompute `meta/stats.json` over the kept parquets only (this is the expensive step; cache it)

See `data_collection_v2/pipeline/lerobot_v2_writer.py` for the exact schema. The CLI command `pixi run python -m data_collection_v2.cli report --output <dir>` does an *in-place* rebuild for a single half — useful as a snapshot trick, but doesn't help with merge.

## Surprises to know about

- **`engine_results/bag_trial_*` dirs are deleted** by the v2_entrypoint cleaner (keeps newest 2). The bags are needed only for tier-2 scoring at trial end; once that's done they're dead weight. If you need to replay one trial, you can't — the bag is gone.
- **`info.json.tmp` permission errors** at host-side finalize are benign — the container already wrote the real `info.json` as root.
- **`scoring` is null in manifest rows during a live run** — it's backfilled at session end when the engine writes `engine_results/scoring.yaml`. For mid-run snapshots, scores aren't available yet (see [`05_keystone_playbook.md` Phase 4](../07_team/05_keystone_playbook.md)).
- **Camera resolution is 256×256** (downsampled from 1152×1024 source). Set your policy's vision encoder input to 256×256 to avoid silent resize.

## Where the data CAME from (so you can re-collect if needed)

If the keystone is corrupted, lost, or you want a different DR envelope:
1. Read [`05_keystone_playbook.md`](../07_team/05_keystone_playbook.md)
2. The configs are `data_collection_v2/configs/keystone_{a,b}.yaml`
3. The policy used is `data_collection_v2.policy.FastCheatCode` — a fork of `aic_example_policies.ros.CheatCode` with TF-based early-exit when the plug tip reaches the port
4. Total cost: ~12 h wall on 2 machines (1:2 split), ~25 GB final parquets, ~5 GB intermediate logs
