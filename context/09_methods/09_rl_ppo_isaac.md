# PPO + Isaac Lab — RL From Scratch with Massive Parallelism

## TL;DR

**PPO** is the on-policy RL workhorse used by virtually every NVIDIA contact-rich manipulation paper (Factory, IndustReal, AutoMate, FORGE, MatchMaker). Combined with **Isaac Lab's thousands of parallel envs**, it can train a contact-rich insertion policy from scratch in **8-10 hours on an RTX 4090** at ~8192 envs. On our **RTX 2000 Ada (16 GB sm_89)**, expect ~2,048-4,096 envs for a state-based task, ~256-1,024 for RGB observations, and roughly **3-6× the wall-clock** of the published RTX 4090 numbers. Strong in theory; the **sim-to-Gazebo gap is the dominant practical risk** — almost everything in the published literature jumps Isaac → real, never Isaac → Gazebo.

## Why this could work for AIC

- **Demonstrated sub-mm clearance** on similar tasks (Factory peg-in-hole 0.104 mm, IndustReal 80%+ real-robot success, AutoMate 100% connectors).
- **Massive parallelism** (4096 envs) means even slow learning is fast in wall-clock.
- **Free of demos.** No data-collection prerequisite; the policy explores.
- **Best-engineered RL stack in robotics.** rsl-rl + Isaac Lab is the practical Pareto frontier for on-policy contact-rich RL.
- **Eureka-friendly.** Reward design is the bottleneck; an LLM (Eureka, file `11` in 10_data) can iterate quickly.

## Why this could fail for AIC (skeptical)

- **Sim-to-Gazebo is the killer.** Factory/IndustReal succeeds because their PhysX-tuned contact behaviour transfers to NIST boards in real life. **Gazebo's contact model differs from Isaac PhysX.** If we train an Isaac policy that exploits Isaac quirks, it won't transfer to our Gazebo eval. **Mitigation**: aggressive DR + sim-to-sim validation as we go, plus considering Gazebo-native RL.
- **Reward shaping for contact-rich is famously hard.** Most published recipes were tuned by human researchers over weeks. Eureka helps but isn't magic.
- **On-policy means sample-inefficient** at the algorithm level. Parallelism compensates but on 16 GB Ada (slower than 4090) the wall-clock cost is real: **maybe 1-3 days** for one good policy run.
- **Image-based observations** in Isaac eat memory fast; 16 GB caps us at maybe ~256-1024 RGB envs. State-based (privileged) policies are easier but don't deploy.
- **No native demos**, so we waste the most valuable asset we have (the keystone CheatCode dataset).
- **Generalization is dataset-dependent**. RL from scratch generalizes only as well as the training distribution. Aggressive randomization helps but reward engineering must remain stable across the distribution.

## Generalization analysis

| Axis | Generalizes? | Notes |
|---|---|---|
| NIC index 0–4 | strong with DR | Randomize NIC index during training. |
| Board pose & yaw | strong with DR | Same. |
| Plug type (SFP/SC) | weak natively; needs goal conditioning | Add task token to obs. |
| Grasp-pose noise | strong | RL with F/T learns to react. |
| Lighting / texture | strong with image-aug DR | Standard. |
| Sim-to-real (Phase 2) | strong; the published recipe | IndustReal/Factory have demonstrated this. |
| Sim-to-Gazebo (Qualification) | **unknown / poor without explicit DR** | The big risk axis. |

## Pipeline sketch

```
Isaac Lab (4k parallel envs):
  • UR5e + Hand-E + task board + cable (SDF-driven contact)
  • Domain randomization: friction, mass, controller stiffness, action latency, F/T noise
  • Observation: image (optional) + F/T + joints + TCP + privileged state (port pose, only for critic if asymmetric)
  • Action: Cartesian impedance delta
  • Reward: -‖plug_tip - port‖² + insert_bonus - force_excess + smoothness_bonus

PPO (rsl-rl): 200-400M env steps → trained policy

Sim-to-sim validation in Gazebo (headless, scoring.yaml):
  if Tier 3 < target → tighten DR or re-train
```

## Key resources

| Resource | Year | What |
|---|---|---|
| Mittal et al., "Isaac Lab" | 2025 | arXiv 2511.04831; the official framework paper. |
| Makoviychuk et al., "Isaac Gym" | 2021 | arXiv 2108.10470 — the predecessor. |
| Schulman et al., "PPO" | 2017 | arXiv 1707.06347 — the algorithm. |
| Narang et al., "Factory" | 2022 | RSS 2022; the Isaac-Gym contact-rich substrate. arXiv 2205.03532 |
| Tang et al., "IndustReal" | 2023 | The cleanest sub-mm-clearance recipe. arXiv 2305.17110 |
| Tang et al., "AutoMate" | 2024 | Multi-geometry generalist; 100 different assembly tasks. RSS 2024 |
| Noseworthy et al., "FORGE" | 2024-25 | Force-conditioned PPO for snap-fit connectors. arXiv 2408.04587 |
| **Isaac Lab repo** | maintained | <https://github.com/isaac-sim/IsaacLab>. CUDA 12, sm_89. |
| **rsl-rl** | maintained | <https://github.com/leggedrobotics/rsl_rl> — the PPO trainer Isaac Lab uses. |
| skrl | maintained | <https://github.com/Toni-SM/skrl> — alternative trainer. |

## Data needs

- **No demos required.**
- **Reward function** = the hand-crafted contract between us and the policy. This is where time goes.
- **Distribution = whatever we randomize.** DR breadth = generalization breadth.
- **Collection strategy** (in the sense of where the data comes from): [`../10_data/04_online_isaac_parallel.md`](../10_data/04_online_isaac_parallel.md).
- **Overlap**: only with other RL methods. Doesn't reuse the keystone IL dataset (which is its main weakness in our setting).

## Compute & time

- **Isaac install + environment setup**: 1-2 person-days. Heavy.
- **PPO training, 200M steps, 4k envs, state-based**:
  - RTX 4090: ~8 h.
  - **RTX 2000 Ada**: ~24-48 h estimated.
- **PPO training, 100M steps, 1k envs, RGB**: ~48-72 h on RTX 2000 Ada.
- **Inference**: ~5 ms / step. Free.

## Best simulation environment

**Isaac Lab for training** — Isaac's parallelism is the entire reason to pick this method. **Gazebo for validation** as you go. If Gazebo eval drops, tighten DR and re-train.

Alternative: **Gazebo-only RL** (no Isaac at all). Slow per-env, but zero sim-to-sim risk. Use this if Isaac setup proves painful. Sample budget shrinks to ~1-10M steps; only feasible with off-policy methods like RLPD ([[hybrid-demo-rl]] file `22`).

## Auto-research applicability

**High fit** — but expensive per iteration.

Tunable axes:
- Reward component weights (Eureka does this for us)
- DR distribution (DrEureka does this)
- Network architecture
- PPO hyperparameters (LR, GAE, entropy coeff)
- Parallel env count (compute-bound)
- Observation subset (image / F/T / state)

Each iter: 24-48h training + 1h sim-to-sim eval = ~30 h. Karpathy fit: **medium-high** — well-suited to overnight batches of 1-2 configs, less suited to fast rapid sweeps. **Eureka** ([`../10_data/11_auto_eureka.md`](../10_data/11_auto_eureka.md)) and **DrEureka** are the specific autoresearch instantiations.

## My note: top-30 probability — **low-moderate**

For our setting (sim-to-Gazebo, 16 GB Ada, small team), the engineering investment is large and the **sim-to-sim gap** is the single biggest unknown.

**Best case** (Isaac → Gazebo transfer works + DR tight + reward well-shaped): 60-70 Tier 3 / trial × 3 = 180-210 → top-30 plausible.

**Likely case** (transfer half-works): 30-50 / trial → mid-pack.

**Worst case** (transfer fails badly): bottom of the pack.

**Path to top-30**:
1. Build the Isaac Lab cable-insertion env (1-2 weeks engineering).
2. Get a Factory/IndustReal-style PPO policy training cleanly in Isaac.
3. Aggressive DR + sim-to-sim Gazebo validation throughout.
4. Add Eureka loop for reward iteration.
5. **Most likely path**: PPO in Isaac → **transfer-via-residual** (file `10`), where the residual is fine-tuned in Gazebo on top of the Isaac PPO base.

## Priority for our project — **4 of 5**

- High setup cost relative to other methods.
- Sim-to-Gazebo gap is the structural risk.
- Best used as a **secondary / experimental track**, not primary.
- Caveat: if our IL methods plateau and Phase 2 (real robot) becomes a real concern, PPO-in-Isaac is the natural sim-to-real path; revisit then.

## Cross-refs

- Variants: [[rl-residual]] (file `10`) — same algorithm with a base layer; lower risk.
- Demo-bootstrap: [[hybrid-demo-rl]] (file `22`) — off-policy alternative.
- Auto reward gen: [[auto-eureka]] ([`../10_data/11_auto_eureka.md`](../10_data/11_auto_eureka.md)).
- Data source: [[online-isaac-parallel]] ([`../10_data/04_online_isaac_parallel.md`](../10_data/04_online_isaac_parallel.md)).
- Sim-to-sim validation: [[online-gazebo-auto]] ([`../10_data/05_online_gazebo_auto.md`](../10_data/05_online_gazebo_auto.md)).
- DR layer: [[synthetic-dr]] ([`../10_data/08_synthetic_dr.md`](../10_data/08_synthetic_dr.md)).
