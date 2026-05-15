# Training — Strategy Overview

Source: [`docs/qualification_phase.md`](../../docs/qualification_phase.md) §A note on simulation, `aic_utils/`.

## What "training" means here

We **cannot** train inside the eval container — its job is to score, not to host learners. Training happens in:

| Stack | What | Where the data comes from |
| --- | --- | --- |
| **Gazebo** (in `aic_eval`) | Verify physics; collect teleop demos | Same simulator as eval — cleanest sim-to-eval transfer |
| **Isaac Lab** ([aic_isaac](../../aic_utils/aic_isaac/)) | High-throughput parallel training (RSL-RL); teleop with spacemouse / XR | Generates demos and RL trajectories |
| **MuJoCo** ([aic_mujoco](../../aic_utils/aic_mujoco/)) | Lightweight rollouts; better contact model for some tasks | Demos via teleop + scripted controllers |
| **LeRobot** (host pixi env) | Imitation training (ACT, Diffusion Policy, etc.) on collected demos | Eats datasets produced by the above |

## Why three simulators?

The challenge organizers explicitly recommend **domain randomization across simulators**. Physics differs between Gazebo / MuJoCo / Isaac in non-trivial ways for contact-rich tasks. Training across all three gives a "free" sim-to-sim-to-real bridge.

For us: prioritize Gazebo first (matches eval). If we have bandwidth, add MuJoCo or Isaac for randomization.

## The data flow

```
                       teleop / script               LeRobot trainer
   Gazebo scene  ───►  demonstrations (parquet) ──►  trained policy ──►  ROS aic_model
       │                                                      ▲
   Isaac scene   ───►  demonstrations / rollouts ─────────────┘
   MuJoCo scene  ───►  demonstrations ──────────────────────────
```

## Where the assets come from

- World state saved by Gazebo to `/tmp/aic.sdf` on spawn → can be imported by IsaacLab / MuJoCo workflows.
- MuJoCo conversion script: `aic_utils/aic_mujoco/scripts/add_cable_plugin.py` (splits SDF→MJCF, adds motors / mimic gripper / FT sensor / cable physics).
- IsaacLab side has its own asset packs (Intrinsic_assets) — see `aic_utils/aic_isaac/README.md`.

## Picking a paradigm

| Paradigm | What we need | Pros | Cons |
| --- | --- | --- | --- |
| **Behavior cloning (ACT)** | A bunch of teleop demos | Closest to RunACT baseline; LeRobot infra is ready | Demands many demos; brittle to OOD |
| **Diffusion policy** | Same demos as ACT | More multimodal, smoother | Heavier inference cost |
| **Reinforcement learning** | Reward function in Isaac Lab + rsl-rl | Doesn't need demos | Sim-to-eval gap larger, longer training |
| **Autoencoder + low-dim policy** | Demos OR random rollouts + ground-truth target | Compact latent → small policy head → fast at inference | Need to design the latent to capture port location |

Our project name says **autoencoder**. The pragmatic plan:
1. Pre-train an image autoencoder on Gazebo (and ideally Isaac/MuJoCo) wrist-camera images.
2. Train a small policy head on top of latent + F/T + joint state, with imitation from CheatCode or teleop demos.
3. Or: condition the autoencoder reconstruction on target port type / location to force the latent to encode the relevant info.

See [`../07_team/00_approach.md`](../07_team/00_approach.md) for the current plan.

## Compute budget

- One Gazebo instance ≈ 1 GPU.
- Isaac Lab in parallel mode can run 256–4096 envs on an L4 → strong RL throughput.
- LeRobot training on demos: a single L4 / 4090 trains ACT in hours for this scale.

## Reward / signal sources

| Source | What it tells you | Available where |
| --- | --- | --- |
| `/scoring/tf` ground truth | Exact plug-port error | Training only (off-limit at eval) |
| Engine's per-trial `scoring.yaml` | Final score | After a trial run |
| F/T sensor | Contact present? Force magnitude | Always |
| Vision (cameras) | Visual servo signal | Always |

For training reward shaping, use ground truth liberally — that's the *whole* point of training mode.

## Next reading

- [`01_teleop_data.md`](./01_teleop_data.md) — keyboard teleop + recording
- [`02_lerobot.md`](./02_lerobot.md) — imitation learning stack
- [`03_isaac_lab.md`](./03_isaac_lab.md) — NVIDIA stack
- [`04_mujoco.md`](./04_mujoco.md) — MuJoCo stack
- **[`05_keystone_dataset.md`](./05_keystone_dataset.md)** — the FastCheatCode-generated keystone dataset (paths, schema, filter rules)
- **[`06_local_eval_loop.md`](./06_local_eval_loop.md)** — how to test a trained policy against `aic_eval` before portal submit
- **[`07_first_pass_recipe.md`](./07_first_pass_recipe.md)** — concrete first-pass training recipe (ACT, hyperparams, packaging)
