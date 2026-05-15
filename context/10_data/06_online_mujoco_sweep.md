# Online Sim Data — MuJoCo CPU Sweeps

## TL;DR

Use MuJoCo as a **cheap CPU-based regression simulator** for fast IL training data sweeps or RL prototyping. Conversion utility exists (`aic_utils/aic_mujoco/scripts/add_cable_plugin.py` patches Gazebo SDF → MJCF). Throughput ~200 episodes/hour on the Xeon CPU. **Not eval-faithful** (cable physics differs from Gazebo), so use only for (a) fast regression CI, (b) world-model RL where MuJoCo is the only reasonable choice, (c) cross-sim DR for the AE / encoder pretrain.

## What it produces

- Format: LeRobot v2 parquet.
- Modalities: same as Gazebo — RGB (simulated), F/T (MuJoCo sensor), joints, action.
- Throughput: ~200 episodes/hour (CPU-bound; doesn't need GPU).

## How automatic? — fully automatic

Python orchestration; no human in loop. Faster startup than Gazebo (no GUI overhead).

## Distribution properties

- **Different cable physics** than Gazebo. Insertion success thresholds may shift.
- **Different visual rendering** — flatter, no GI. Vision-trained policies may not transfer.
- **Same robot model** (UR5e + Hand-E URDF, MJCF-converted). Joint kinematics match.

## Pipeline sketch

```
1. Convert Gazebo SDF → MJCF (one-time, via aic_mujoco scripts).
2. Patch cable physics + actuators + F/T (via add_cable_plugin.py).
3. Launch MuJoCo + ros2_control with our standard policy + engine.
4. Loop episodes, log parquet.
```

Existing pieces:
- `aic_utils/aic_mujoco/scripts/` — conversion utility.
- `aic_utils/aic_mujoco/launch/` — ros2 launch files.
- LeRobot teleop / recording works in MuJoCo (per the `aic_mujoco` README).

## Storage + naming convention

```
/data/aic_mujoco/<experiment_id>/episode_<seed>.parquet
```

Mark `sim=mujoco` in episode metadata so mixed-source training can filter.

## Which methods consume this

| Method | How |
|---|---|
| [[rl-world-models]] (11) | ★ TD-MPC2 / DreamerV3 prefer MuJoCo over Gazebo for throughput. |
| [[repr-autoencoder]] (17), [[repr-mae]] (19) | Cross-sim image variety for encoder robustness. |
| [[il-*]] (02-08) | Auxiliary data; not primary (sim-to-eval gap). |
| autoresearch CI | Fast regression check — does our pipeline still produce sensible behaviour? |

## Compute & time

- CPU only; doesn't compete with GPU work.
- 1000 episodes in ~5 hours.

## Quality gates

- Episode success rate sane (CheatCode should still succeed in MuJoCo).
- F/T signatures qualitatively similar to Gazebo (don't expect identical numbers).

## Failure modes

- **Sim-to-Gazebo skill leakage.** A policy trained on MuJoCo may exploit MuJoCo-specific contact behaviours.
- **MJCF conversion bugs** — meshes / collision shapes may not match Gazebo exactly. Visual sanity check after every conversion.

## Why we treat as secondary

- Not eval-faithful.
- Slower than Isaac at GPU-scale parallelism.
- Most valuable as **regression CI** (fast check) and **encoder cross-sim variety** (visual robustness for AE).

## Cross-refs

- Primary online sim: [[online-gazebo-auto]] ([`./05_online_gazebo_auto.md`](./05_online_gazebo_auto.md)).
- GPU-parallel alternative: [[online-isaac-parallel]] ([`./04_online_isaac_parallel.md`](./04_online_isaac_parallel.md)).
- Consumers: [[rl-world-models]] (file `11`), [[repr-autoencoder]] (file `17`), [[repr-mae]] (file `19`).
