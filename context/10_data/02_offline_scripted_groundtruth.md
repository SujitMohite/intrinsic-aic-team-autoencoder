# Auto-Collected Scripted CheatCode Demos — the keystone pipeline

## TL;DR

Run `CheatCode.py` (or any ground-truth-driven scripted controller) headlessly in Gazebo, sweeping every randomization axis the eval will use, and log `(observation, action, scoring outcome)` tuples to parquet. This is the **single highest-leverage data action** in the entire project: one pipeline whose output feeds 12+ of the methods we're evaluating, generated **without a human in the loop**.

CheatCode uses `/scoring/tf` ground truth, which is **forbidden at eval but permitted during training**. The data this produces does NOT contain ground-truth labels in the policy inputs — only in the auxiliary supervision targets. So a policy trained on this data does not violate the rules.

## What it produces

- **Format**: parquet datasets in the LeRobot v2 format (so `lerobot-train` can consume directly).
- **Modalities per timestep**:
  - `obs.left_image`, `obs.center_image`, `obs.right_image` — RGB 1152×1024 (downsample to 256×256 at write time to save disk).
  - `obs.wrist_wrench` — 6-vec force/torque.
  - `obs.joint_states` — 6-vec joint positions + velocities.
  - `obs.tcp_pose` — extracted from `controller_state` (6-DoF).
  - `action.cartesian_delta` — 6-vec Cartesian command in `gripper/tcp` frame.
  - `action.stiffness` — 6-vec (we set this per command).
- **Per-episode metadata**:
  - Trial id, NIC index, board pose, port name, plug type.
  - Grasp-noise sample (the actual delta applied this episode).
  - Success / Tier-3 outcome (from `scoring.yaml`).
  - **Ground-truth labels** (for aux losses): port pose in `base_link`, plug-tip pose, depth-into-port. *These live in metadata, NOT in the policy-input columns.*
- **Order-of-magnitude size**: 5000 successful episodes × ~150 timesteps × ~3 MB / step compressed ≈ **2 TB raw → ~200 GB after image compression + selective image storage** (e.g. only keep 1 in 3 frames of side cameras).

## How automatic? — **fully automatic**

Zero human-in-loop after pipeline startup. The pipeline:

1. Launches headless Gazebo (no GUI, no RViz) inside the `aic_eval` container.
2. Launches the engine with a custom config sweeping the randomization grid.
3. Launches `aic_model` with `policy:=aic_example_policies.ros.CheatCode` (or our own scripted variant).
4. Records sensor + action streams via a small recorder node (or `lerobot-record` with our adapter).
5. Writes per-episode parquet + dataset card metadata.
6. Loops on the next config in the sweep.

**Throughput on our desktop (Xeon + RTX 2000 Ada 16 GB)**:
- ~50 episodes / hour at 1.0 RTF (each episode ~30 s sim + 30 s startup/teardown).
- With a "fast mode" patch (skip Gazebo GUI, disable GI, reduce camera resolution at collection time, skip the inter-trial reset wait), we can hit ~100 ep/hr.
- 5000 episodes → 50–100 hours wall-clock. Run overnight × 3 nights.

## Distribution properties

What it covers naturally:
- **NIC index** (0–4): trivial — set in the sweep config.
- **Board pose & yaw**: set in the sweep config; sample uniformly over the documented ranges (see [`../01_environment/02_task_board.md`](../01_environment/02_task_board.md)).
- **Rail translation / NIC yaw offset**: same — uniform sweep.
- **Plug type**: spin SFP trials and SC trials in the sweep.
- **Grasp-pose noise**: documented as ~2 mm / 0.04 rad; sample uniformly.

What it misses (and we'll add via [`08_synthetic_dr.md`](./08_synthetic_dr.md)):
- **Lighting variation** — Gazebo's GI is fixed by default. Add programmatic lighting permutations.
- **Texture variation** — cable color, board color, NIC card materials. Augmentation in image space is cheaper than re-running Gazebo.
- **Camera intrinsics jitter** — no need at Qualification; consider for Phase 2.
- **CheatCode-specific failure modes** — CheatCode succeeds nearly every time (it cheats). The dataset is biased toward "successful" trajectories. **Mitigation**: instrument CheatCode to occasionally make controlled errors (over/under-shoot, premature insertion attempt) so the policy learns to recover. Or seed with WaveArm-like exploration for the first N seconds.

## Pipeline sketch (plain prose; no code yet)

```
[ Sweep generator ]                       generates configs (NIC, board, plug, grasp_noise)
        │
        ▼
[ Trial launcher ]                        starts headless Gazebo + engine + aic_model(CheatCode)
        │
        ▼
[ Recorder ]                              subscribes to /observations, /aic_controller/{pose,joint}_commands
                                          flushes per-timestep rows to a buffer
        │
        ▼
[ Per-trial finalizer ]                   on engine 'task_completed':
                                          - reads scoring.yaml
                                          - writes per-episode parquet
                                          - writes per-episode metadata.json
                                          - moves on to next config
        │
        ▼
[ Sweep orchestrator ]                    increments seed; on N done, terminates
```

Existing toolkit pieces we'll reuse:
- `aic_training_utils/aic_training_gz_bringup.launch.py` — already wires up Gazebo + `/expand_xacro` for programmatic spawning. See [`../01_environment/01_scene.md`](../01_environment/01_scene.md).
- `/expand_xacro` — programmatic task-board / cable spawn from launch params.
- `aic_engine` configurable via custom YAML — set per-trial randomization.
- `aic_example_policies/aic_example_policies/ros/CheatCode.py` — the scripted policy we'd start from.
- `lerobot_robot_aic` package — adapter that lets `lerobot-record` see our ROS topics. The cleanest route for parquet output.

What we'd *write*: a thin Python orchestrator that loops over a config grid, launches the trial subprocess, waits, and reads `scoring.yaml`. Hundreds of lines, not thousands.

## Storage + naming convention

```
/data/aic_demos/
├── manifest.json                                  global dataset card
├── splits/
│   ├── train_v1.jsonl                             episode ids
│   └── val_v1.jsonl
└── episodes/
    └── 2026-05-15_seed-0001/
        ├── episode.parquet                        timesteps
        ├── metadata.json                          per-episode info
        ├── images/                                optional: raw images if not embedded in parquet
        └── scoring.yaml                           the engine's output
```

Naming convention per episode:
```
ep_<sim>_<plug>_<NIC>_<board-yaw-bucket>_<seed>.parquet
e.g. ep_gz_sfp_nic2_yaw45_s00471.parquet
```

The bucketed names let us quickly slice by axis ("give me all SC episodes with NIC index 3") without scanning metadata.

Storage location on the desktop: `/data/aic_demos/`. Mirror to an external SSD weekly. **Do not put under the repo** — too big for git, breaks pixi.

## Which methods consume this

Direct primary fit (★ = highest dependence):

| Method | How it uses this data |
|---|---|
| [[il-bc]] (02) | ★ Demos for vanilla BC |
| [[il-act]] (03) | ★ Action-chunked supervised learning |
| [[il-diffusion-policy]] (04) | ★ Demos for diffusion conditional |
| [[il-vqbet]] (05) | ★ Demos for VQ-BeT |
| [[il-force-aware]] (06) | ★ Demos with F/T included |
| [[il-3d]] (07) | Optional — needs depth/points (derived from stereo) |
| [[il-equivariant]] (08) | ★ Same demos, different policy class |
| [[rl-residual]] (10) | Demos as warm start for the base policy + replay buffer |
| [[rl-hil-serl]] (12) | ★ Imitation pretrain stage of HIL-SERL |
| [[repr-autoencoder]] (17) | Optional — observation slice serves AE pretraining |
| [[repr-mae]] (19) | Optional — same |
| [[hybrid-classical-learned]] (21) | ★ Training data for the learned residual head |
| [[hybrid-demo-rl]] (22) | ★ Demonstrations for DAPG / DDPGfD / AWAC / RLPD |

That's **8 primary + 5 secondary methods** fed by one pipeline. If we build this well, almost everything else accelerates.

## Compute & time

- Per-episode cost on the desktop: ~30 s sim + 30 s overhead = 1 min.
- Storage: ~50 MB / episode after compression (most cost is images; F/T+joints are tiny).
- 5000 episodes: ~50 GB / ~85 hours wall-clock at default settings; ~25 GB / ~50 hours with "fast mode".
- We can start training methods on a partial dataset; checkpoint the dataset every 1000 episodes.

## Quality gates (what we check before declaring a dataset "good")

Run after each sweep batch:

1. **Coverage check**: every (NIC index × plug type × yaw bucket) combination has ≥ 50 episodes.
2. **Success rate**: ≥ 90% of episodes had `tier_3.score > 50` (CheatCode should succeed nearly always; if not, our scripted controller has a bug or the engine config is wrong).
3. **Action distribution**: histograms of Cartesian deltas show non-degenerate spread; no axis is identically zero.
4. **Observation freshness**: no missing frames; image timestamps monotonically increase; F/T tare offsets sane.
5. **Failure-mode sample**: hand-inspect 5 random failed episodes to confirm they're real failures, not pipeline bugs.
6. **Held-out split**: reserve 10% of NIC indices or yaw buckets as a generalization-test split *that we never train on*.

If any gate fails: **fix the pipeline and re-run before training anything downstream**. Bad data wastes more time than the re-run.

## Failure modes (what goes wrong silently)

- **CheatCode succeeds via TF teleport-like trajectories that are *physically* impossible.** If CheatCode applies large stiffness with TF-derived setpoints, the impedance controller will execute it but a learned policy without TF can never reproduce that path. **Mitigation**: cap stiffness in the scripted policy so it's within what a learner could realistically command.
- **The cable physics softlock**. Sometimes Gazebo's cable model gets into a weird state; the trial hangs. Add a per-episode timeout + reset.
- **F/T baseline drift across episodes** if we don't tare correctly. The engine tares before each trial in eval; we must do the same in collection.
- **RTF drift** when running 3 simulation instances in parallel for throughput. Sim time will look fine in scoring.yaml but real Gazebo physics may degrade. Solo-instance collection is slower but cleaner.
- **The detector dataset coupling**: if we also use this run to label port-detector training data, a CheatCode bug that mis-localizes the port silently corrupts the detector training set. Add a sanity check that the recorded port pose matches the ground-truth from `/scoring/tf`.

## Cross-refs

- Distribution targets: [[distribution-design]] ([`./09_distribution_design.md`](./09_distribution_design.md)).
- DR layer on top: [[synthetic-dr]] ([`./08_synthetic_dr.md`](./08_synthetic_dr.md)).
- Auto-pipeline infrastructure: [[auto-pipeline-design]] ([`./10_auto_pipeline_design.md`](./10_auto_pipeline_design.md)).
- Auto-research loop wraps this pipeline as its data step: [[auto-research-loop]] ([`./12_auto_research_loop.md`](./12_auto_research_loop.md)).
- Primary consumers: [[il-bc]], [[il-act]], [[il-diffusion-policy]], [[il-vqbet]], [[il-force-aware]], [[il-equivariant]], [[rl-residual]], [[rl-hil-serl]], [[hybrid-classical-learned]], [[hybrid-demo-rl]].
