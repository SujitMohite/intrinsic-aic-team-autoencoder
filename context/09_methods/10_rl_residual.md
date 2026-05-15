# Residual RL — learn a correction on top of a classical or IL base

## TL;DR

**A learned policy outputs a *delta* on top of a hand-coded or pretrained baseline controller.** The base policy (impedance controller, visual servo, or frozen IL policy) handles the easy 95% of the task; the residual closes the contact-rich endgame. Documented result: **ResiP** (Ankile et al. 2024) takes FurnitureBench BC peg-in-hole success from **5% → 99%** at 0.2 mm tolerance by attaching a residual PPO head to a frozen diffusion-policy base. **The structurally safest, fastest-to-converge, lowest-sim-to-sim-risk RL approach in our list.**

## Why this could work for AIC

- **Base controller does the heavy lifting.** A classical impedance + visual-servo approach can get us within a few mm of the port. A small residual then handles 5 mm → 0 mm.
- **Sample efficiency.** ResiP fine-tunes in 20-100M env steps; much less than RL-from-scratch.
- **Sim-to-eval friendly.** The base controller is identical between sims (it's just impedance control + visual servoing). The residual is small, so the sim-to-sim gap is small.
- **Safety by construction.** Residual is bounded; if the residual head fails or hallucinates, the base controller still produces a reasonable action.
- **F/T-friendly.** Residual head typically conditions on F/T — that's exactly where the base controller's open-loop logic is weakest.
- **Composable with IL.** "Train BC base + train residual" is the proven recipe.

## Why this could fail for AIC (skeptical)

- **Requires a credible base controller.** If the visual-servo approach in [[classical]] (file `01`) doesn't land within a few mm, the residual has too much work to do. Builds dependency: classical pipeline must already be working.
- **Reward design still required.** Less brittle than from-scratch RL (because the base provides a warm start), but the residual reward still needs to capture "Tier-3 partial insertion progress."
- **The Isaac → Gazebo gap matters at the residual scale.** If the residual learns to exploit Isaac contact quirks, it may misbehave in Gazebo. Mitigation: train in Gazebo directly (slower) or use Isaac → Gazebo DR.
- **Reported numbers are on *frozen base + residual on a peg in sim*** — not directly on our randomized cable-insertion problem. Optimistic but unproven for us.

## Generalization analysis

| Axis | Generalizes? | Notes |
|---|---|---|
| NIC index 0–4 | strong if base handles it | The base controller is the generalizer; residual just refines. |
| Board pose & yaw | strong | Same. |
| Plug type (SFP/SC) | moderate; needs base controller to handle both | Two-base + single-residual or one-base-with-task-cond. |
| Grasp-pose noise | **very strong** | This is exactly what residual RL is supposed to fix. F/T-driven residual = perfect fit. |
| Lighting / texture | strong (if base is force-driven) | Base often doesn't use vision in the endgame; residual is vision-light. |
| Sim-to-eval | moderate-strong | Smaller policy = smaller drift. |

## How it works (architectural sketch)

```
Observation → π_base(obs)  →  a_base  (e.g. classical impedance + visual servo)
                                 │
                            (+) ───── + a_residual = a_final → robot
                                 │
Observation → π_residual(obs)  → a_residual ~ N(0, σ_clip)  (small RL head)
```

Common base choices:
1. **Classical: visual-servo + impedance** (file `01` minus the FSM).
2. **Frozen IL: a trained BC / ACT / DP policy** that has gotten us close.
3. **Frozen pretrained encoder + linear head** as a structured base.

Residual RL training:
- **Algorithm**: PPO (Johannink 2018 used DDPG; ResiP 2024 uses PPO; HIL-SERL uses RLPD-SAC for the online stage).
- **Action bound**: |a_residual| ≤ small (e.g. ±2 cm Cartesian, ±5° rotation). Hard clipping keeps the policy safe.
- **Reward**: dense — proximity to port (training time only, ground-truth allowed) + force penalty + success bonus.
- **Critic**: takes full obs (including F/T) + concatenated `a_base` as input. Critic learns "given the base action, how good is this residual?"

## Key resources

| Resource | Year | What |
|---|---|---|
| Johannink et al., "Residual Reinforcement Learning for Robot Control" | 2018 | The OG. arXiv 1812.03201. ICRA 2019. |
| Ankile et al., "From Imitation to Refinement — Residual RL for Precise Visual Assembly" (ResiP) | 2024 | The killer reference: 5% BC → 99% residual on 0.2 mm FurnitureBench. arXiv 2407.16677. |
| **ResiP code**: `ankile/robust-rearrangement` | maintained | <https://github.com/ankile/robust-rearrangement> — built on IsaacGymEnvs + robomimic. |
| Schoettler et al., "Deep Reinforcement Learning for Industrial Insertion Tasks with Visual Inputs and Natural Rewards" | 2019 | Foundational sim-to-real insertion RL. |
| FORGE (Noseworthy et al. 2024-25) | 2024-25 | Force-conditioned PPO for snap-fit connectors; closely related. arXiv 2408.04587 |
| HIL-SERL is essentially residual-RL-from-IL-base | 2024 | See [[rl-hil-serl]] (file `12`). |

## Data needs

- **For the base controller**: depends on which base.
  - Classical: no training data needed; tuning only.
  - IL base: same demos as [[il-act]] / [[il-diffusion-policy]] / [[il-force-aware]].
- **For the residual RL**: online rollouts in sim. No demos required (the base IS the warm start). ~20-100M env steps.
- **Reward signal**: dense reward using `/scoring/tf` ground truth during training. Critical that the reward isn't gameable. **Specifically: reward = -‖plug_tip - port_target‖ + α·success_flag − β·force_excess.**
- **Collection strategy**: [`../10_data/05_online_gazebo_auto.md`](../10_data/05_online_gazebo_auto.md) (if training in Gazebo) or [`../10_data/04_online_isaac_parallel.md`](../10_data/04_online_isaac_parallel.md) (if training in Isaac for throughput).

## Compute & time

- **Base training** (if IL): 4-8 hours (per [[il-act]] etc.).
- **Residual training**:
  - In Isaac (4k parallel envs): ~4-8 hours for 100M steps.
  - In Gazebo (sequential): ~24-72 hours for 1-10M steps (Gazebo is slow at single-env throughput).
- **Inference**: base + small residual head. Total ~10-15 ms / step.
- **VRAM**: comfortable in 16 GB. Base policy (frozen) + critic + actor.

## Best simulation environment

- **Train in Gazebo** if engineering time is short: zero sim-to-sim gap.
- **Train in Isaac Lab** for throughput, then sim-to-sim validate in Gazebo with aggressive DR. Higher ceiling.
- **MuJoCo** as a regression sanity check.

ResiP's published numbers are on Isaac → real; the Isaac → Gazebo direction is *easier* (both are sim).

## Auto-research applicability

**High fit.**

Tunable axes:
- Residual clip magnitude (1, 2, 5 cm; 1, 5, 10°)
- PPO hyperparameters (LR, GAE, entropy)
- Base policy choice (classical FSM / IL-frozen)
- Reward shaping coefficients (proximity, force, time)
- F/T input to residual on/off
- Action representation (Cartesian / joint)

Iteration: residual training is 4-8 hours per config. Karpathy fit: **high** for sweep over reward coefficients (Eureka-style) and clip magnitudes.

## My note: top-30 probability — **moderate-high**

- **Best case**: Classical base + F/T-residual converges → ~70 Tier 3 / trial × 3 = 210, plus Tier 2 ~20 each → **270 total**. Top-30 strong.
- **Likely case**: IL base + residual → ~60 Tier 3 / trial × 3 = 180, Tier 2 ~15 → **225 total**. Top-30 plausible.
- **Worst case**: residual fails to bridge a weak base → ~30 / trial = 90. Mid-pack.

**Path to top-30**:
1. Build a working classical base or IL-base ([[il-force-aware]]).
2. Define a clean dense reward in Gazebo (auto-collected from `/scoring/tf`).
3. Train residual in Gazebo for 1-2M steps (slow but eval-faithful) OR Isaac + DR for 100M steps then validate in Gazebo.
4. Evaluate; tune reward weights with Eureka-style ([[auto-eureka]] [`../10_data/11_auto_eureka.md`](../10_data/11_auto_eureka.md)).

**Risk factors**: reward hacking ("policy hangs out near the port to maximize proximity reward without inserting"), unstable training near contact phase, Isaac → Gazebo drift if not validated.

## Priority for our project — **2 of 5**

The lowest-risk RL approach we have. Best deployed as a **refinement layer** on top of an already-working IL or classical base.

## Cross-refs

- Base options: [[classical]] (file `01`), [[il-act]] / [[il-diffusion-policy]] / [[il-force-aware]] (files `03`/`04`/`06`).
- Closely related: [[rl-hil-serl]] (file `12`) — HIL-SERL is essentially residual-SAC-from-IL-warm-start with humans in the loop.
- Demo-bootstrapped RL family: [[hybrid-demo-rl]] (file `22`).
- Reward auto-generation: [[auto-eureka]] ([`../10_data/11_auto_eureka.md`](../10_data/11_auto_eureka.md)).
- Sim envs: [[online-isaac-parallel]] / [[online-gazebo-auto]].
- The exact "ResiP" stack in this repo: clone `ankile/robust-rearrangement` as a reference implementation; we adapt the residual-PPO head onto our task.
