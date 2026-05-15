# Online Sim Data — Isaac Lab Parallel Rollouts

## TL;DR

Spin up thousands of parallel Isaac Lab environments on one GPU to generate online RL data at massive throughput. **Best for RL methods** (PPO, SAC, residual-RL, demo-bootstrapped). NOT good for IL: Isaac's contact behaviour differs from Gazebo, so demos generated here may not transfer perfectly to our eval. **Use exclusively for online RL training, and validate the resulting policy against Gazebo** as part of the loop.

## What it produces

- **Format**: in-memory rollouts (don't usually persist to disk — RL trainers consume directly).
- **If we persist** (for RLPD / demo-bootstrap): LeRobot v2 parquet, same schema as offline.
- **Modalities**: state + privileged ground-truth (for asymmetric critics) + optional image rendering.
- **Throughput**: 1,000+ episodes / hour at 4k parallel envs on our 16 GB GPU.

## How automatic? — fully automatic

Isaac Lab + rsl-rl trainers run unattended for hours/days. No human in loop.

## Distribution properties

- **Cover whatever we randomize.** DR breadth = data breadth.
- **Isaac PhysX contact model.** Will not exactly match Gazebo. We mitigate via DR.
- **Privileged state available** (port pose, plug pose) — useful for asymmetric critic but cannot enter the policy observation.

## Pipeline sketch

```
Build Isaac Lab cable-insertion env:
  ├ UR5e + Hand-E URDF
  ├ Task board USD (convert from Gazebo SDF or rebuild)
  ├ SFP/SC cable USDs
  ├ Contact dynamics tuned (Factory-style)
  ├ DR ranges: friction, mass, stiffness, F/T noise, action latency
  └ Reward: dense or sparse + classifier

Spawn 4096 envs, train PPO with rsl-rl, log to W&B, checkpoint every N steps.
```

Existing toolkit pieces:
- `aic_utils/aic_isaac/` — NVIDIA-prepared Isaac Lab integration. Has assets and scripts.
- IsaacLab `rsl-rl` trainer.
- Asset conversion: Isaac USD ↔ Gazebo SDF, available via `aic_mujoco/scripts/`-like utilities or NVIDIA's USD converter.

## Storage + naming convention

For RL: usually transient (replay buffer). For persisting checkpoints:
```
/data/aic_isaac/runs/<exp_id>/
├── policy_*.pt
├── stats.csv
└── tensorboard/
```

## Which methods consume this

| Method | How |
|---|---|
| [[rl-ppo-isaac]] (09) | ★ Primary substrate. |
| [[rl-residual]] (10) | Base + residual training. |
| [[rl-world-models]] (11) | Less ideal (TD-MPC2 single-env), but workable. |
| [[hybrid-demo-rl]] (22) | RLPD online phase. |

## Compute & time

- Isaac env setup: 1-2 person-weeks (cable physics + DR are non-trivial).
- Training time: see [[rl-ppo-isaac]] (file `09`) — 24-48 hours per policy on RTX 2000 Ada.

## Quality gates

- **Sim-to-sim validation against Gazebo** at every N checkpoints. If Gazebo eval drops, tighten DR.
- Reward components monitored per episode; reward hacking detected via Tier-3 collapse.
- Action saturation checks (clipping rates).

## Failure modes

- **Isaac quirks leak into the policy.** Mitigation: aggressive DR + Gazebo regression.
- **Memory leaks** with many envs. Mitigation: cap envs, restart trainer periodically.
- **Asset mismatch between Isaac and Gazebo.** Mitigation: convert from the same source (URDF/MJCF) and validate visually.
- **Reward design absorbs most engineering time.** Mitigation: Eureka ([`./11_auto_eureka.md`](./11_auto_eureka.md)).

## Cross-refs

- Primary consumer: [[rl-ppo-isaac]] (file `09`).
- DR layer: [[synthetic-dr]] ([`./08_synthetic_dr.md`](./08_synthetic_dr.md)).
- Sim-to-sim validation: [[online-gazebo-auto]] ([`./05_online_gazebo_auto.md`](./05_online_gazebo_auto.md)).
- Reward auto-gen: [[auto-eureka]] ([`./11_auto_eureka.md`](./11_auto_eureka.md)).
