# Hybrid: Demo-Bootstrapped RL — DAPG / DDPGfD / AWAC / RLPD / IBRL

## TL;DR

A family of methods that **inject demonstrations into off-policy RL** to handle sparse rewards on contact-rich tasks. The umbrella covers: **DDPGfD** (pre-fill replay with demos), **DAPG** (BC-shaped auxiliary loss on NPG), **AWAC** (advantage-weighted regression), and the current SoTA **RLPD** (off-policy SAC + 50% demo sampling + Q-ensembling + layer norm + image augmentation). RLPD's child **HIL-SERL** (covered in file `12`) is the closest published method to our task. This file covers the broader family at a paradigm level: **when we want RL but don't want to start from scratch, this is the family**.

## Why this could work for AIC

- **Demos give a warm start;** RL refines beyond what demos alone achieve.
- **Sparse / terminal rewards** are no longer fatal — the demo replay buffer always has positive examples.
- **Sample efficiency.** RLPD halves prior data + online budgets on standard benchmarks.
- **F/T native** — at least in the RLPD/SERL line.
- **Pairs naturally with our keystone pipeline** ([`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md)) — demos are already there.
- **Algorithmically converges on HIL-SERL** for the close-tolerance regime — gives us a fallback in case the HIL-SERL port is too engineering-heavy.

## Why this could fail for AIC (skeptical)

- **Off-policy RL is finicky with image inputs in Gazebo.** Per-step compute is the bottleneck; running thousands of parallel envs (Isaac's strength) doesn't compose with off-policy gradient updates as cleanly as on-policy PPO.
- **Demos must be "good enough" but not "too good".** If CheatCode demos succeed every time, the policy has no failure-mode signal to learn from. **Mitigation**: inject controlled perturbations in CheatCode (over/undershoot, premature insertion attempts).
- **Reward design is still required.** Cleaner than from-scratch RL but not free. The dense-reward designs in HIL-SERL are well-engineered; we'd inherit them.
- **JAX-native repos.** RLPD, SERL, HIL-SERL are JAX. Our pixi env is PyTorch-default. Adapter cost ~1 person-week.
- **Reported numbers** are on Adroit, AntMaze, V-D4RL — different task class than cable insertion. The HIL-SERL line is the only direct evidence on our task type.

## Generalization analysis

Same general profile as [[rl-hil-serl]] (file `12`) — RL with image + F/T generalizes well across NIC indices and grasp noise when data covers it. See file 12 for the per-axis breakdown.

## Family members compared

| Method | Year | Best for | Limitation |
|---|---|---|---|
| **DDPGfD** (Vecerik 2017) | 2017 | Sparse-reward continuous control with demos | Old; DDPG instability |
| **DAPG** (Rajeswaran 2018) | 2018 | Dexterous hand manipulation | On-policy; less sample-efficient than off-policy |
| **AWAC** (Nair 2020) | 2020 | Offline pretraining + light online fine-tune | Sometimes underperforms vs RLPD on harder tasks |
| **RLPD** (Ball 2023) | 2023 | The current SoTA off-policy demo-bootstrapped method | Implementation complexity (UTD, ensembling, aug) |
| **IBRL** (Imitation-Bootstrapped RL) | 2024 | RLPD variant with explicit BC warm start | Newer, less battle-tested |
| **EXPO** (Expressive Policies) | 2025 | Expressive (diffusion) actors in off-policy RL | Slow inference; experimental |
| **HIL-SERL** | 2024 | Closest published analog to our task | Real-only published; needs porting (see file `12`) |

For AIC, **RLPD or HIL-SERL-style SERL (sans human)** is the practical choice. Everything else is for context.

## Architectural sketch (RLPD / SERL minus HIL)

```
Replay buffer:
  • 50% sampled from demo pool (file 02 dataset)
  • 50% sampled from online RL rollouts

SAC actor: ResNet-10 image encoder + F/T history + state → policy μ, σ
SAC critic ensemble (5-10):  same encoder + action → Q-value

Update:
  • UTD ratio 5-10 (gradient steps per env step)
  • Layer norm everywhere
  • Image augmentation (random crop + color jitter)
  • Target entropy automatic

Reward:
  • Sparse: classifier on terminal frame → +1 (success) / 0 (fail), OR
  • Dense (training only, ground-truth): -‖plug_tip - port_target‖² + bonuses

Termination: success classifier fires OR step limit OR force excess
```

## Key resources

| Resource | Year | What |
|---|---|---|
| Vecerik et al., "DDPGfD" | 2017 | arXiv 1707.08817 |
| Rajeswaran et al., "DAPG" | 2018 | arXiv 1709.10087. <https://github.com/aravindr93/hand_dapg> (mostly historical) |
| Nair et al., "AWAC" | 2020 | arXiv 2006.09359. Implemented in d3rlpy (PyTorch). |
| Ball et al., "RLPD" | 2023 | arXiv 2302.02948. <https://github.com/ikostrikov/rlpd> (JAX, light maintenance but functional). |
| Luo et al., "HIL-SERL" | 2024 | See file `12`. |
| Luo et al., "SERL" (non-HIL) | 2024 | arXiv 2401.16013. <https://github.com/rail-berkeley/serl> |
| IBRL (Imitation Bootstrapped RL) | 2024 | RLPD with explicit BC warm start. |
| d3rlpy library | maintained | PyTorch implementations of AWAC, IQL, CQL. <https://github.com/takuseno/d3rlpy> |

## Data needs

- **Demo pool**: 30-100 demos from our keystone pipeline. **Same data as IL methods** — full reuse.
- **Reward signal**: either a small reward classifier (~100 labels, auto-generated from `scoring.yaml`) or a dense ground-truth-based reward (training only).
- **Online rollouts**: 20-50k steps in Gazebo (slow but eval-faithful) or 100-500k in Isaac (fast, then sim-to-sim validate).
- **Distribution requirements**: demos cover all eval-time variation.
- **Collection strategy**:
  - Demos: [`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md).
  - Online: [`../10_data/05_online_gazebo_auto.md`](../10_data/05_online_gazebo_auto.md) or [`../10_data/04_online_isaac_parallel.md`](../10_data/04_online_isaac_parallel.md).
- **Overlap**: demo pool shared with all IL methods. ★

## Compute & time

- **Demo prep**: same as keystone pipeline.
- **Reward classifier**: 15 minutes.
- **Online RL** (Gazebo, 30k steps): 2-4 hours wall-clock.
- **Online RL** (Isaac, 500k steps): 4-6 hours.
- **VRAM**: 4-8 GB. Comfortable.

## Best simulation environment

- **Gazebo** for sim-to-eval faithfulness.
- **Isaac Lab** for throughput, then sim-to-sim validate in Gazebo with aggressive DR.

## Auto-research applicability

**High fit.**

Tunable axes:
- UTD ratio (1, 3, 5, 10)
- Demo/online sampling ratio
- Critic ensemble size
- Image augmentation strength
- Reward shaping coefficients
- Choice of (DAPG / AWAC / RLPD / IBRL)

Iteration: 2-4 hours per online run. ~5/day. Karpathy fit: **high** — clear tunable knobs, fast measurable signal.

## My note: top-30 probability — **high**

When [[rl-hil-serl]] (file `12`) is too engineering-expensive to port, this is the practical fallback that hits 80% of HIL-SERL's strength.

**Best case** (RLPD-style + good demos + Gazebo online + DR): 65-75 Tier 3 / trial × 3 = 195-225, Tier 2 ~20 → **245-275**. Top-30 likely.

**Likely case**: 50-65 Tier 3 → **190-225**.

**Path to top-30**: see [[rl-hil-serl]] (file `12`); this is the same architecturally minus the human.

## Priority for our project — **2 of 5**

- Best as the **second-stage RL** on top of an IL base (similar to HIL-SERL minus human).
- Same engineering cost as HIL-SERL; same value. Pick this if HIL-SERL's human-in-loop concept is too costly.
- ★ Pairs naturally with our autoresearch loop ([[auto-research-loop]] [`../10_data/12_auto_research_loop.md`](../10_data/12_auto_research_loop.md)).

## Cross-refs

- Closest specific instance: [[rl-hil-serl]] (file `12`).
- Residual variant: [[rl-residual]] (file `10`).
- Base IL options: [[il-act]] (file `03`), [[il-diffusion-policy]] (file `04`), [[il-force-aware]] (file `06`).
- Demo data: [[offline-scripted-groundtruth]] ([`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md)).
- Online infrastructure: [[online-gazebo-auto]] / [[online-isaac-parallel]].
- Reward generation: [[auto-eureka]] ([`../10_data/11_auto_eureka.md`](../10_data/11_auto_eureka.md)).
