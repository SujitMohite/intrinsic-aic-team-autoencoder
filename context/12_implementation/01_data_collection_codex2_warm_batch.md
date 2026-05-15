# Data Collection Codex2 Warm-Batch Pipeline

STATUS: implementation plan accepted

## Summary

`data_collection_codex2/` is the fresh Codex-owned implementation of the 24-hour
keystone data pipeline. It collects scripted `CheatCode` demonstrations in
headless Gazebo while keeping the evaluation stack warm for a configurable
batch of trials. The upstream `aic_engine` already supports multi-trial configs
and resets the spawned task board, cable, robot, and lifecycle model state
between trials, so this pipeline uses that surface instead of relaunching
Gazebo for every episode.

The implementation intentionally does not modify `aic_engine`, `aic_controller`,
`aic_scoring`, `aic_interfaces`, or existing `data_collection*` folders.

## Architecture

```text
data_collection_codex2.orchestrator
  read sweep YAML
  generate seeded TrialConfig objects
  group into BatchSpec objects
  render one multi-trial engine YAML per batch
  launch /entrypoint.sh in the aic_eval distrobox
  wait for the in-container Zenoh router
  start one host aic_model process with CheatCode
  record /observations and command topics
  split episodes by /insert_cable/_action/status
  parse batch scoring.yaml
  append manifest rows
  write coverage and quality reports
```

The important throughput choice is one engine/model launch per batch. Within a
batch, `aic_engine` calls `reset_after_trial()`, deactivates/reactivates
`aic_model`, deletes trial entities, homes the robot, respawns the next scene,
and writes a single batch-level `scoring.yaml`.

## Public Interfaces

Main CLI:

```bash
PYTHONPATH=. pixi run python -m data_collection_codex2.orchestrator \
  --sweep data_collection_codex2/configs/default_24h.yaml
```

Smoke CLI:

```bash
bash data_collection_codex2/scripts/run_smoke.sh
```

Dry-render validation:

```bash
bash data_collection_codex2/scripts/dry_render.sh
```

## Storage Contract

```text
<output_dir>/
  manifest.jsonl
  coverage_report.json
  smoke_analysis.json
  batches/
    batch_s000001_s000025/
      batch_metadata.json
      engine_config.yaml
      engine.log
      model.log
      results/scoring.yaml
  episodes/
    ep_gz_sfp_nic2_p1_s000017/
      planned_trial.json
      metadata.json
      episode.parquet
  logs/
    orchestrator.log
```

The parquet schema is intentionally simple and local to this repo. It contains
JPG-compressed wrist-camera observations, force/torque, joint state, TCP state,
the latest robot command, task identifiers, seed, and action goal UUID.

## Auto-Research Smoke Loop

The smoke loop is limited to pipeline verification, not method research. It
runs the smoke config under a watchdog, classifies failure modes from manifests
and logs, and writes deterministic JSON reports. It does not modify code itself;
Codex reads the report and patches only `data_collection_codex2/`.

Watchdog signals:

- global smoke timeout
- no output directory growth
- no manifest growth
- stale observation heartbeat
- missing scoring
- zero-row episodes
- lifecycle/model discovery errors
- router/Zenoh startup errors

## Assumptions

- ROS 2 Kilted and `rmw_zenoh_cpp` are used.
- The `aic_eval` distrobox container exists and exposes `/entrypoint.sh`.
- The host Pixi environment can run `aic_model` and import `cv2`, `pyarrow`,
  `numpy`, and `yaml`.
- `CheatCode` may use training-only ground truth; recorded policy inputs remain
  observations/actions/scores, not hidden evaluation transforms.
- Batch size defaults to 25 for throughput and 5 for smoke tests.

