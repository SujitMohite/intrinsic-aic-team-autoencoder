# RL with World Models — TD-MPC2 + DreamerV3

## TL;DR

**Learn a world model first; do RL in the model's imagination.** **TD-MPC2** (Hansen 2024) does short-horizon MPC inside a learned latent space with a TD-trained value backing up beyond the horizon — SOTA on 104 continuous-control tasks. **DreamerV3** (Hafner 2023/2025) is the recurrent latent-state world model that the 2025 Nature publication generalized to one hyperparameter set across very diverse domains. Both are **extraordinarily sample-efficient at the algorithm level** — orders of magnitude fewer env steps than PPO. **But neither has been shown to handle contact-rich sub-cm insertion**, and both run single-env-sequential (no parallel-Isaac throughput advantage). For AIC: theoretically appealing, practically uncertain.

## Why this could work for AIC

- **Sample efficiency.** TD-MPC2 might solve a cm-scale insertion in 500k–1M env steps. Compared to PPO's 200M.
- **Image + F/T fusion is natural.** Concat into the world model's input; the recurrent dynamics learn temporal structure of force events.
- **One hyperparameter set.** DreamerV3's headline is "no tuning across domains" — useful when our engineering budget is thin.
- **Better than PPO for partial-observability tasks.** The recurrent state handles temporal F/T patterns.

## Why this could fail for AIC (skeptical)

- **Contact discontinuities are exactly where latent dynamics struggle.** Both world models assume smooth dynamics; insertion's "first-contact" event is a discontinuity in F/T space.
- **No published sub-cm insertion result** for either. DreamerV3 on robot manipulation is Meta-World / RLBench territory (coarser).
- **No Isaac Lab integration** for either. Both run sequentially per env. We lose Isaac's parallelism advantage.
- **Per-step compute is high.** TD-MPC2 inference: short MPC rollouts add latency. DreamerV3 inference: small but the world model itself is heavy at training.
- **Sim-to-Gazebo gap is high.** World models implicitly fit the training-sim's dynamics; transferring the *learned model* to Gazebo's contact behaviour is non-trivial.

## Generalization analysis

| Axis | Generalizes? | Notes |
|---|---|---|
| NIC index | with DR | Standard. |
| Board pose & yaw | with DR | Standard. |
| Plug type | weak; needs goal conditioning | Standard. |
| Grasp-pose noise | strong | F/T-aware world model learns recovery. |
| Lighting | depends on encoder | Standard. |
| Sim-to-eval | weak | World model can overfit training-sim contact. |

## Key resources

| Resource | Year | What |
|---|---|---|
| Hansen et al., "TD-MPC2" | 2024 | arXiv 2310.16828. <https://github.com/nicklashansen/tdmpc2> |
| Hafner et al., "DreamerV3" (Nature 2025) | 2023-25 | arXiv 2301.04104. <https://github.com/danijar/dreamerv3> |
| HarmonyDream | 2024 | ICML 2024; task-harmonised loss weights for Dreamer. |
| DreamerV3-XP | 2025 | Better exploration. |
| TDMPBC | 2025 | Self-imitative TD-MPC variant. |

## Data needs

- **None up front.** RL learns via env interaction.
- **Optional demo bootstrap.** Both methods can use demos to fill replay; not standard but plausible.
- **Collection strategy**: [`../10_data/06_online_mujoco_sweep.md`](../10_data/06_online_mujoco_sweep.md) (fastest for world-model RL) or [`../10_data/05_online_gazebo_auto.md`](../10_data/05_online_gazebo_auto.md) (eval-faithful but slow).

## Compute & time

- TD-MPC2 / DreamerV3: ~1-3 days on the desktop for a single task at 500k-1M steps.
- VRAM: 4-12 GB. Comfortable.

## Auto-research applicability — **medium**

Long iterations limit sweep throughput. Each config is a 1-3 day training run.

## My note: top-30 probability — **moderate**

Speculative bet. If contact discontinuities work better than expected and sim-to-eval transfer works, this is a strong sample-efficient path. If either fails, it's a wasted week.

**Best case**: 50-65 Tier 3 / trial → 150-200 total. Mid-pack to lower top-30.

**Risk factors**: no published evidence on our task class.

## Priority for our project — **4 of 5**

Defer. Revisit if [[rl-residual]] (file `10`) or [[rl-hil-serl]] (file `12`) demonstrate that RL is the right paradigm and we want maximum sample efficiency. **Otherwise skip.**

## Cross-refs

- Alternative RL: [[rl-ppo-isaac]] (file `09`), [[rl-residual]] (file `10`), [[rl-hil-serl]] (file `12`), [[hybrid-demo-rl]] (file `22`).
- MuJoCo sim: [[online-mujoco-sweep]] ([`../10_data/06_online_mujoco_sweep.md`](../10_data/06_online_mujoco_sweep.md)).
