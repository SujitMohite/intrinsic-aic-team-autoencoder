# Data Collection Pipeline — Design Document (v1)

> **Purpose**: turn `context/10_data/02_offline_scripted_groundtruth.md` from prose into a concrete buildable system.
>
> **Status**: v1 design. Targets the 24-hour multi-machine plan ([`../11_24h_strategy/03_multimachine_24h.md`](../11_24h_strategy/03_multimachine_24h.md)). Single-machine fallback is the same code, single-process.

## Goal

Produce **1500-2500 labeled episodes** (obs, action, score) by running the upstream `CheatCode.py` policy headlessly in Gazebo across the full eval-time randomization grid. Output format consumable by **LeRobot training** and **our F/T-ACT** train script. Fully automatic; no human after launch.

## Non-goals (v1)

- F/T-reactive CheatCode modification (a v2 follow-up).
- Multi-instance Gazebo (v2; v1 is single Gazebo per process).
- Cross-machine coordination (v2; v1 is per-machine self-contained; USB sync is manual).
- LeRobot v2 dataset format compliance (v1 uses our own simple parquet schema that's *convertible* to LeRobot v2; not the same on disk).
- Image-only self-supervised collection mode (separate pipeline).

## System architecture

```
┌──────────── orchestrator (Python, our code) ────────────┐
│                                                          │
│  1. read sweep config (default_sweep.yaml)               │
│  2. for each trial in sweep:                             │
│       a. randomize TrialConfig                           │
│       b. write per-trial engine YAML to /tmp             │
│       c. start_trial() on recorder                       │
│       d. launch (subprocess) eval stack                  │
│       e. wait for completion or timeout                  │
│       f. end_trial() on recorder                         │
│       g. parse scoring.yaml                              │
│       h. append manifest row                             │
│       i. cleanup subprocesses                            │
│  3. quality_gate check every N trials                    │
│                                                          │
│  ROS 2 node embedded:                                    │
│    - subscribes to /observations, /aic_controller/*      │
│    - on start_trial: open new parquet writer             │
│    - on each Observation: append row                     │
│    - on end_trial: flush + close                         │
└──────────────────────────────────────────────────────────┘
       │ subprocess.Popen
       ├──────────────────────────┬──────────────────────┐
       ▼                          ▼                      ▼
   ros_gz_sim + aic_engine    aic_model              rmw_zenohd
   (via aic_bringup           (via pixi run          (auto-managed
   launch file)               ros2 run aic_model)    by ros2_run)
```

### Why subprocess-per-trial (not persistent process)

Pros (our choice):
- Trivial cleanup: process tree dies, state is gone.
- No state-leak bugs between trials.
- Matches the engine's own design: it processes ONE config file and exits.

Cons (accepted):
- ~20-30 s subprocess startup overhead per trial (vs ~5 s for persistent).
- Caps throughput around 60 ep/h on a single machine.

We accept the throughput hit for v1 reliability. The plan's stated target (50-100 ep/h) is met.

### Why embedded ROS node, not separate recorder subprocess

The orchestrator already runs rclpy (to talk to the action server and check engine state). Adding subscriptions to /observations + command topics is cheap. A separate recorder subprocess would need its own Zenoh peer + sync mechanism.

## Per-trial flow

```
T+0       orchestrator selects randomize TrialConfig
T+1       write /tmp/aic_trial_<id>.yaml (engine config with this trial)
T+2       recorder.start_trial(ep_id, ep_dir)
T+3       Popen #1: aic_bringup aic_gz_bringup.launch.py
              gazebo_gui:=false
              launch_rviz:=false
              ground_truth:=true                # CheatCode needs /scoring/tf
              start_aic_engine:=true
              aic_engine_config_file:=/tmp/aic_trial_<id>.yaml
              shutdown_on_aic_engine_exit:=true
              AIC_RESULTS_DIR=<ep_dir>
T+5       Popen #2: pixi run ros2 run aic_model aic_model --ros-args
              -p use_sim_time:=true
              -p policy:=aic_example_policies.ros.CheatCode
T+8       (engine waits for model discovery, transitions configure→activate)
T+15      (engine sends InsertCable goal)
T+20-45   (CheatCode runs the insertion; recorder captures observations and actions)
T+50      engine writes scoring.yaml; Popen #1 exits cleanly
T+51      orchestrator detects exit; sends SIGTERM to Popen #2
T+53      recorder.end_trial(); flushes parquet
T+54      orchestrator reads scoring.yaml; appends manifest row
T+55      next trial
```

Total per-trial wall-clock: **~55 s** at RTF 1.0. → ~65 ep/h ceiling.

### Detection of "trial done"

Three signals, in order of reliability:

1. **Primary**: Popen #1 (aic_engine process) exits with rc=0. The `shutdown_on_aic_engine_exit` flag in `aic_gz_bringup.launch.py` triggers `EmitEvent(Shutdown(...))` when engine exits cleanly — the whole launch process exits.
2. **Secondary**: `scoring.yaml` appears in `AIC_RESULTS_DIR`. We confirm parse succeeds.
3. **Watchdog**: per-trial timeout (default 90 s wall-clock). If neither primary nor secondary fires, kill subprocess tree and mark trial as `invalid`.

## TrialConfig — what we randomize

```python
@dataclass
class TrialConfig:
    ep_id: str                                # ep_gz_sfp_nic2_s00471
    plug_type: Literal["sfp", "sc"]
    port_name: str                            # sfp_port_0 / sfp_port_1 / sc_port_0 / sc_port_1
    target_module_name: str                   # nic_card_<i> or sc_port_<i>
    nic_card_index: int | None                # 0-4 (SFP trials only)
    nic_rail: str | None                      # nic_rail_<i>
    nic_rail_translation_m: float             # in [-0.022, +0.022]
    nic_card_yaw_offset_rad: float            # in [-0.17, +0.17] (≈10°)
    sc_rail: str | None                       # sc_rail_<0,1> (SC trial only)
    sc_rail_translation_m: float | None       # in [-0.06, +0.055]
    task_board_x: float                       # in eval-config range
    task_board_y: float
    task_board_z: float
    task_board_yaw: float
    grasp_offset_x: float                     # ±2 mm
    grasp_offset_y: float
    grasp_offset_z: float
    grasp_offset_rpy: tuple[float, float, float]
    cable_type: str = "sfp_sc_cable"
    time_limit_s: int = 180
    seed: int
```

Sweep generator produces TrialConfig instances using **stratified random sampling**: each axis is drawn independently per trial. Categorical axes (NIC index, plug type) are weighted to hit minimum counts (see `09_distribution_design.md`).

## Engine YAML generation

The engine wants a YAML file like `aic_engine/config/sample_config.yaml`. We generate per-trial YAMLs containing exactly ONE trial — derived from a template (`templates/single_trial_template.yaml`) with substitution.

Why one trial per config: each engine invocation runs the entire trial list in sequence, then writes a single `scoring.yaml`. We want per-trial isolation + per-trial scoring file. So one engine invocation = one trial.

## Recorder design

Single `Recorder(rclpy.Node)` instance, alive for the orchestrator's lifetime. Subscribes to:
- `/observations` (`aic_model_interfaces/msg/Observation`) — **primary heartbeat at 20 Hz**.
- `/aic_controller/pose_commands` (`aic_control_interfaces/msg/MotionUpdate`) — latest Cartesian command (held).
- `/aic_controller/joint_commands` (`aic_control_interfaces/msg/JointMotionUpdate`) — latest joint command (held).

On each `/observations` callback (20 Hz):
1. If `not active`: drop.
2. Else: snapshot latest action command + serialize row to in-memory buffer.

On `end_trial()`:
1. Flush buffer to `episode.parquet` in episode directory.
2. Reset action holders.

Image storage: **inline JPG bytes in parquet column**. Three columns (left/center/right), JPG quality 85, downsampled to 256×256 at write time (configurable). ~10 KB per image × 3 = 30 KB per row × ~600 rows = ~18 MB per episode. 1500 episodes → ~27 GB.

Parquet row schema:

| Column | Type | Description |
|---|---|---|
| `t_sim_ns` | int64 | Sim time, nanoseconds |
| `t_wall_ns` | int64 | Wall clock, nanoseconds |
| `step` | int32 | Step counter within episode |
| `left_image_jpg` | bytes | JPG-encoded image |
| `center_image_jpg` | bytes | |
| `right_image_jpg` | bytes | |
| `ft_force_x/y/z` | float32 × 3 | Force at wrist |
| `ft_torque_x/y/z` | float32 × 3 | Torque at wrist |
| `joint_position_<6>` | float32 × 6 | UR5e joints |
| `joint_velocity_<6>` | float32 × 6 | |
| `tcp_position_x/y/z` | float32 × 3 | TCP pose from controller_state |
| `tcp_orientation_x/y/z/w` | float32 × 4 | |
| `tcp_velocity_lin_x/y/z` | float32 × 3 | TCP twist |
| `tcp_velocity_ang_x/y/z` | float32 × 3 | |
| `action_mode` | int8 | 1=Cartesian, 2=Joint, 0=none yet |
| `action_pose_pos_x/y/z` | float32 × 3 | If mode=1 |
| `action_pose_ori_x/y/z/w` | float32 × 4 | |
| `action_velocity_lin_x/y/z` | float32 × 3 | |
| `action_velocity_ang_x/y/z` | float32 × 3 | |
| `action_stiffness_diag_<6>` | float32 × 6 | Diagonal of 6×6 stiffness |
| `action_damping_diag_<6>` | float32 × 6 | |
| `action_traj_mode` | int8 | 1=velocity, 2=position |
| `action_joint_<6>` | float32 × 6 | If mode=2 |
| `action_joint_vel_<6>` | float32 × 6 | |

## Storage layout

```
/data/aic_demos/                              configurable
├── manifest.jsonl                            one row per trial
├── coverage_report.json                      regenerated on every quality gate
├── episodes/
│   └── ep_<sim>_<plug>_<NIC>_<seed>/
│       ├── episode.parquet
│       ├── metadata.json                     trial config + scoring summary
│       └── scoring.yaml                      engine output (copied here)
└── logs/
    ├── orchestrator.log
    └── trial_<seed>.log
```

`manifest.jsonl` row schema:

```json
{
  "ep_id": "ep_gz_sfp_nic2_s00471",
  "trial_config": {...},                   // full TrialConfig as JSON
  "scoring": {
    "tier_1_valid": 1,
    "tier_2": {...},
    "tier_3_score": 47.2,
    "tier_3_outcome": "partial",
    "total": 79.4
  },
  "wall_clock_s": 52.7,
  "rtf_mean": 0.94,
  "valid": true,
  "n_rows": 612,
  "parquet_path": "episodes/ep_gz_sfp_nic2_s00471/episode.parquet",
  "completed_at_iso": "2026-05-14T18:23:17Z"
}
```

## Failure handling

Categorized; each has automatic policy:

| Failure | Symptom | Auto-action |
|---|---|---|
| Engine timeout (model never discovered) | Engine process exits with non-zero rc | Mark trial invalid, log reason, continue |
| Gazebo crash | Engine still alive but no /observations heard for 10 s | SIGTERM all subprocesses, mark invalid, restart pipeline |
| Cable softlock (trial hangs) | Wall-clock > 90 s with engine still running | SIGTERM subprocesses, mark invalid, continue |
| Recorder crash (rclpy callback throws) | Exception bubbles to executor | Log, drop the row, continue (don't kill trial) |
| Disk full | Parquet write fails | Pause orchestrator, alert via stderr |
| RTF below 0.3 sustained | Per-trial wall-clock vs expected | Add warning to manifest; continue |
| `scoring.yaml` missing or invalid | Parse fails | Mark invalid, keep parquet for debug, continue |

Restart-resilience: orchestrator reads existing manifest at startup. Skips episodes already present. Resumes from next config.

## Sweep config schema

```yaml
# data_collection/configs/default_sweep.yaml

output_dir: /data/aic_demos
target_total_episodes: 2000
seed_start: 1

# Per-axis sampling weights (categorical) and ranges (continuous)
plug_distribution:
  sfp: 0.60
  sc: 0.40

nic_card_index_distribution:    # only used for SFP trials
  uniform_over: [0, 1, 2, 3, 4]

sc_port_distribution:           # only used for SC trials
  uniform_over: [0, 1]

nic_rail_translation_range_m: [-0.022, 0.022]
nic_card_yaw_offset_range_rad: [-0.17, 0.17]
sc_rail_translation_range_m: [-0.06, 0.055]

task_board_x_range: [0.25, 0.35]
task_board_y_range: [-0.15, -0.05]
task_board_z_range: [1.15, 1.25]
task_board_yaw_range: [0.0, 1.5708]    # 0 to 90°

grasp_offset_xyz_sigma_m: [0.002, 0.002, 0.002]
grasp_offset_rpy_sigma_rad: [0.04, 0.04, 0.04]

# Headless / fast-mode flags passed to launch
gazebo_gui: false
launch_rviz: false
disable_gi: true                # patched into aic.sdf at startup
camera_downsample_hw: [256, 256]

# Per-trial timeouts
per_trial_wall_clock_timeout_s: 90
model_discovery_timeout_s: 30
model_configure_timeout_s: 60

# Quality gates
quality_gate_every_n_episodes: 100
min_success_rate: 0.85
min_per_nic_demos: 40
min_per_plug_demos: 250
```

## Quality gates (every N episodes)

```
1. Coverage:
   - Each plug type has ≥ min_per_plug_demos / total * collected so far episodes.
   - Each NIC index 0-4 (within SFP) has ≥ min_per_nic_demos episodes.
2. Trial success rate: count of (tier_3_score > 50) / total ≥ min_success_rate.
3. Action distribution: each axis of Cartesian deltas has nonzero variance.
4. F/T presence: at least 50% of episodes show >0.5 N peak force (confirms contact happened).

If any fail: log warning. Don't auto-pause unless success rate < 0.5.
```

## Performance budget (validated against the plan)

| Phase | Wall-clock | Notes |
|---|---|---|
| Per-trial setup (Popen + engine bringup) | 15-20 s | Dominated by Gazebo + engine init |
| CheatCode insertion | ~30 s sim time | At RTF 1.0 → ~30 s wall |
| Per-trial teardown | 3-5 s | Subprocess SIGTERM + cleanup |
| **Total per trial** | **~50-55 s** | At RTF 1.0 |
| Throughput | **~65 ep/h** | Single instance |
| 24h yield | ~1500 ep | Single machine, single instance |

This matches the multi-machine plan's per-instance estimate of 50-80 ep/h (we're at the lower end because subprocess-per-trial loses ~30% to startup vs persistent-process).

## v2 follow-ups (out of scope for v1)

- **Persistent engine process** that processes multiple trials without restart. Throughput → ~100 ep/h. Requires engine modification or wrapper.
- **F/T-reactive CheatCode** (modified policy that backs off on contact force). Critical for force-aware IL training data quality.
- **Multi-instance Gazebo** with isolated Zenoh routers. Throughput → 150 ep/h on a single machine.
- **LeRobot v2 dataset format** native output (vs convertible). Lets `lerobot-train` consume directly.
- **Distributed orchestrator** across machines with shared state. v1 is per-machine independent.
- **Adaptive sampling**: bias toward under-represented buckets after each quality gate.

## File layout (the deliverable)

```
data_collection/
├── README.md                      How to run + configure + debug
├── orchestrator.py                Main entry point (python -m or direct)
├── pipeline/
│   ├── __init__.py
│   ├── config.py                  SweepConfig + TrialConfig dataclasses
│   ├── randomizer.py              Stratified random sampler
│   ├── launcher.py                Subprocess manager
│   ├── recorder.py                rclpy node + parquet writer
│   ├── manifest.py                Append-only JSONL writer + reader
│   └── quality_gates.py           Coverage + success-rate checks
├── configs/
│   ├── default_sweep.yaml         Full 24h target sweep
│   └── smoke_test.yaml            10-episode validation
├── templates/
│   └── single_trial_template.yaml Engine config template (one trial)
└── scripts/
    ├── run_smoke.sh               Quick smoke test
    └── apply_gi_off.sh            Disable global illumination in aic.sdf
```

## How this fits into the broader plan

- This pipeline IS the keystone described in [`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md).
- It feeds the F/T-ACT training script described in [`../11_24h_strategy/02_methods_24h.md`](../11_24h_strategy/02_methods_24h.md) and [`../11_24h_strategy/03_multimachine_24h.md`](../11_24h_strategy/03_multimachine_24h.md).
- Auto-research orchestrator ([`../10_data/12_auto_research_loop.md`](../10_data/12_auto_research_loop.md)) eventually picks training configs whose **input is the manifest** of this pipeline.

## Open questions deferred to v1 implementation

1. **Engine state topic** — does the engine publish a status topic we can subscribe to instead of relying on process exit? If yes, simpler completion detection. v1: rely on process exit.
2. **Zenoh router lifecycle when re-launching aic_model rapidly** — does it cleanly re-register? Might need to start a persistent rmw_zenohd outside the launch tree. v1: let the launch file handle it; observe failures.
3. **GI disable patch** — modify `aic.sdf` in place or via launch arg? Launch file doesn't expose this; v1 patches the file on-disk (idempotent script).
