# Online Sim Data — Headless Gazebo Auto Rollouts

## TL;DR

Run **headless Gazebo** (no GUI, no RViz) in a loop driven by Python orchestration: launch → randomize → run policy → log → reset → repeat. Used for (a) IL fine-tuning / replay augmentation, (b) RL online training in eval-sim, (c) evaluation throughput in the autoresearch loop. **Slower than Isaac (1.0 RTF sequential) but zero sim-to-eval gap**. ~50 episodes/hour per Gazebo instance; we can multi-instance for higher throughput.

## What it produces

- Format: LeRobot v2 parquet (same as keystone offline pipeline).
- Modalities: same — RGB images, F/T, joints, action, plus ground-truth metadata.
- Order-of-magnitude: ~50 episodes / hour per Gazebo instance; ~100-200 / hour with 2-4 parallel headless Gazebo containers.

## How automatic? — fully automatic

Per-trial reset is the only synchronization point; everything else is unattended.

## Distribution properties

- **Matches eval distribution exactly** — same simulator.
- **DR via launch parameters** (see [`./08_synthetic_dr.md`](./08_synthetic_dr.md)).
- **F/T noise matches eval** (no extra adapter needed).

## Pipeline sketch

```
For each config in the sweep:
  1. Launch headless Gazebo with the trial config (via /expand_xacro).
  2. Tare F/T sensor.
  3. Start aic_model with the policy under test.
  4. aic_engine fires InsertCable.
  5. Recorder logs (obs, action, F/T, ...) per timestep to ring buffer.
  6. On task completion or timeout:
     - Flush ring buffer to parquet.
     - Read scoring.yaml.
     - Append to manifest.
  7. Kill containers, move to next config.
```

Existing toolkit pieces:
- `aic_bringup/aic_gz_bringup.launch.py` with `headless:=true` (verify launch arg name).
- `aic_training_utils` for `/expand_xacro` programmatic spawn.
- `aic_engine` for trial orchestration.
- `aic_example_policies` policies (or our own).
- `lerobot-record` adapter via `lerobot_robot_aic`.

What we write: orchestration script (Python, ~200-300 lines) that wraps subprocess launch + sweep config.

## Storage + naming convention

```
/data/aic_online/
└── <experiment_id>/
    ├── episode_<seed>.parquet
    └── manifest.json
```

## Which methods consume this

| Method | How |
|---|---|
| [[il-bc]], [[il-act]], [[il-diffusion-policy]], [[il-vqbet]], [[il-force-aware]] | ★ Replay augmentation / DAgger fine-tune. |
| [[rl-residual]] | Online RL training. |
| [[rl-hil-serl]] | ★ Online RL stage. |
| [[hybrid-demo-rl]] | RLPD online stage. |
| [[auto-research-loop]] | ★ Eval harness uses this as the canonical scoring path. |

## Compute & time

- Per-episode cost: ~30 s sim + 30 s overhead = ~1 min single-instance.
- 4-instance multi-Gazebo on the desktop: ~4 episodes/min if RTF holds.
- 10k episodes: ~40 hours single-instance, ~10 hours quad-instance.

## Quality gates

- RTF ≥ 0.5 throughout (else physics degrades).
- Per-episode scoring.yaml valid + parsed correctly.
- No "stuck" episodes (timeout enforcement).

## Failure modes

- **RTF drift** when multi-instance — physics degrades silently. Mitigation: cap at 2-3 instances, monitor RTF.
- **Gazebo cable softlock** — Gazebo gets into a weird cable state. Mitigation: per-trial timeout + reset.
- **Zenoh disconnects** between instances. Mitigation: separate Zenoh router per instance.
- **Disk fills up fast** with raw images. Mitigation: downsample at write time (256×256) and keep 1-of-3 frames for side cams.

## Cross-refs

- Offline counterpart: [[offline-scripted-groundtruth]] ([`./02_offline_scripted_groundtruth.md`](./02_offline_scripted_groundtruth.md)).
- Eval harness for autoresearch: [[auto-research-loop]] ([`./12_auto_research_loop.md`](./12_auto_research_loop.md)).
- DR overlay: [[synthetic-dr]] ([`./08_synthetic_dr.md`](./08_synthetic_dr.md)).
- Pipeline infra: [[auto-pipeline-design]] ([`./10_auto_pipeline_design.md`](./10_auto_pipeline_design.md)).
