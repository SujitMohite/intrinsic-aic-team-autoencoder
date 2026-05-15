# data_collection_v2 — keystone scripted-CheatCode data pipeline

Implements the keystone pipeline for the 24h plan
([`context/11_24h_strategy/01_data_24h.md`](../context/11_24h_strategy/01_data_24h.md))
following strategy 2
([`context/10_data/02_offline_scripted_groundtruth.md`](../context/10_data/02_offline_scripted_groundtruth.md)).

**Full architecture & rationale**: `/home/smohite/.claude/plans/i-have-done-previously-cheeky-bubble.md`.

## The one-paragraph summary

The engine already loops trials in a single process
(`aic_engine.cpp:583-615`): between trials it deactivates the `aic_model`
lifecycle node, deletes spawned entities, homes the robot, and respawns the next
scene. Gazebo never restarts. **v2 leverages this**: one session = one
`distrobox enter` + one Gazebo + one engine + one `aic_model` + one recorder,
running for hundreds of trials. v1 was respawning the whole stack per trial,
losing ~30 s of headroom each time.

## What this produces

```
<output_dir>/
├── manifest.jsonl                       one row per trial (restart-resilient)
├── coverage_report.json                 regenerated every quality-gate cadence
├── sessions/
│   ├── session_<id>.yaml                full engine config (N pre-randomized trials)
│   └── session_<id>.yaml.trials.jsonl   sidecar: trial_counter -> TrialConfig
├── engine_results/
│   └── scoring.yaml                     session-end engine output (per-trial tiers)
├── logs/
│   ├── session_<id>.log                 container stdout/stderr
│   ├── zenoh.log
│   ├── model.log
│   └── recorder.log
└── lerobot_v2/                          THE TRAINING DATASET
    ├── meta/{info,episodes,tasks,stats}{.json,.jsonl}
    ├── data/chunk-000/episode_NNNNNN.parquet
    └── aux/episode_NNNNNN.parquet       (currently empty placeholder for GT poses)
```

## Quick start

### 0. One-time prerequisites

- `pixi 0.67.2` (per CLAUDE.md §2).
- Docker + NVIDIA Container Toolkit; user in `docker` group (recommended).
- distrobox-created `aic_eval` container — see `docs/getting_started.md`.

### 1. Smoke test (10 trials, ~7 min, lenient gates)

```bash
cd ~/ws_aic/src/intrinsic-aic-team-autoencoder
pixi run python -m data_collection_v2.cli smoke
```

Output lands in `/tmp/aic_v2_smoke/`. Expect ≥ 8/10 episodes with parquet files in
`lerobot_v2/data/chunk-000/`. If anything in the stack is broken, this surfaces it.

### 2. Full session

```bash
pixi run python -m data_collection_v2.cli session \
    --config data_collection_v2/configs/keystone_1500.yaml \
    --output /data/aic_v2/run_$(date +%Y%m%d_%H%M)
```

### 3. Resume after a crash

```bash
pixi run python -m data_collection_v2.cli resume \
    --config data_collection_v2/configs/keystone_1500.yaml \
    --output /data/aic_v2/run_20260514_1200
```

Re-reads `manifest.jsonl`, skips seeds already collected, generates a new
session_<new_id>.yaml with only the missing seeds, and re-enters the container.

### 4. Quality-gate report (no collection)

```bash
pixi run python -m data_collection_v2.cli report \
    --output /data/aic_v2/run_20260514_1200
```

### Hands-off wrapper (Laptop 1 overnight)

```bash
tmux new -s aic_collect
bash data_collection_v2/scripts/run_session.sh keystone_laptop1
# Ctrl-b d to detach
```

## How a session executes

1. Host: `cli.py session` → `session_driver.run_session()`.
2. `session_driver` loads sweep YAML, reads manifest (resume), generates the
   trial list via `pipeline.randomizer.iter_trials`.
3. `pipeline.session_yaml.render_session_config` writes one big engine YAML
   (`sessions/session_<id>.yaml`) with all N trial entries, plus a sidecar
   `.trials.jsonl` mapping trial counter → `TrialConfig`.
4. `distrobox enter aic_eval -- bash data_collection_v2/container/v2_entrypoint.sh`
   (one shot per session).
5. Inside the container, `v2_entrypoint.sh`:
   - starts `rmw_zenohd`,
   - starts `aic_model` (policy=`aic_example_policies.ros.CheatCode`),
   - starts the rclpy recorder (`data_collection_v2_recorder.recorder_node`),
   - `exec`s `ros2 launch aic_bringup aic_gz_bringup.launch.py start_aic_engine:=true ...`.
6. The engine loops through every trial in `session_<id>.yaml`. Between trials
   it does its own `reset_after_trial` (delete entities, home joints, respawn).
7. The recorder hears `/aic_model/transition_event`:
   - `goal=active` → trial start; opens an episode buffer.
   - `goal=inactive` → trial end; flushes one LeRobot v2 parquet + appends
     to `manifest.jsonl`.
8. Host polls `manifest.jsonl` for progress; emits coverage report every
   `quality_gate_every_n_episodes`.
9. When the engine finishes all trials, `shutdown_on_aic_engine_exit:=true`
   tears down the launch tree; the container exits.
10. Host: `_backfill_scoring()` reads `engine_results/scoring.yaml` and merges
    per-trial scores into the manifest; `_finalize_dataset()` writes
    `meta/info.json` + `meta/stats.json`.

## Verification (post-build, before the 24h run)

```bash
# 1. (Optional) patch aic.sdf for GI off.
bash data_collection_v2/scripts/apply_gi_off.sh

# 2. Smoke test.
pixi run python -m data_collection_v2.cli smoke
# Expect: rc=0, manifest.jsonl has 10 lines, lerobot_v2/data/chunk-000/episode_000{000..009}.parquet exist.

# 3. Load the dataset via lerobot (cross-checks the v2 schema).
pixi run python -c "
from lerobot.datasets.lerobot_dataset import LeRobotDataset
ds = LeRobotDataset(repo_id='aic_smoke', root='/tmp/aic_v2_smoke/lerobot_v2', local_files_only=True)
print(f'len={len(ds)} keys={list(ds[0].keys())}')
"

# 4. Trial-boundary sanity (run while smoke is in flight in another terminal).
distrobox enter aic_eval -- bash -lc "source /ws_aic/install/setup.bash && ros2 topic echo /aic_model/transition_event"
# Expect: alternating active/inactive transitions per trial.
```

## Salvaged from data_collection v1

- `pipeline/config.py` — `SweepConfig` + `TrialConfig` dataclasses
- `pipeline/randomizer.py` — stratified random sampler
- `pipeline/manifest.py` — atomic append-only JSONL
- `pipeline/quality_gates.py` — coverage + success-rate checks

## What's NEW in v2

- `pipeline/session_yaml.py` — emits one multi-trial engine YAML (replaces
  v1's per-trial template mutation)
- `pipeline/lerobot_v2_writer.py` — native LeRobot v2 dataset writer
- `recorder/` — ROS 2 Python package; rclpy node listens to
  `/aic_model/transition_event` for trial boundaries
- `container/v2_entrypoint.sh` — one-shot in-container launcher
- `session_driver.py` — host orchestrator (NO per-trial subprocesses)
- `cli.py` — `smoke / session / resume / report`

## Known limitations / TODOs

- LeRobot v2 schema details should be cross-checked against the pinned
  `lerobot` version (`pixi run python -c 'import lerobot; print(lerobot.__version__)'`)
  and adjusted if the installed version expects slightly different field names.
- Auxiliary ground-truth poses (port pose, plug tip, depth-into-port) are NOT
  yet captured. The hooks exist (`aux/` directory + the `aux_rows` arg in
  `WriteSession.write_episode`), but populating them requires subscribing to
  `/scoring/tf` and pulling the named transforms — left for a follow-up so the
  recorder stays lean for the smoke test.
- Multi-instance Gazebo (multiple engines on one machine) is out of scope.
- The `--output` of `resume` must match the prior run's directory; the
  CLI currently asks for `--config` explicitly because we don't yet persist
  the source sweep YAML next to `sessions/` (deferred).

## When to delete v1

Once a clean smoke run produces a valid LeRobot v2 dataset that `lerobot-train`
loads without errors AND a ≥ 100-trial session has produced reasonable coverage
stats, `data_collection/` (v1) can be removed.
