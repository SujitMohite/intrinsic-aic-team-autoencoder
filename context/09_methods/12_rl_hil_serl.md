# HIL-SERL — Human-in-the-Loop Sample-Efficient RL

## TL;DR

**The single most relevant published method for our problem.** HIL-SERL (Luo et al. 2024, Science Robotics 2025) combines **RLPD** (off-policy SAC + 50% demo sampling + Q-ensembling + layer norm + image augmentation) with **human corrections during training**. Demonstrated near-100% success on real-robot tasks that are direct cousins of ours: **USB connector grasp-and-insertion**, **USB cable clip-mounting**, RAM/SSD insertion, timing-belt assembly, dashboard pin insertion — all in 1–2.5 hours of wall-clock real-robot training. Wrist F/T is in the observation by default. **If we adapted this stack to Gazebo, it would be a credible primary path to top-30.**

## Why this could work for AIC

- **Closest published analog.** USB connector insertion is the closest pre-existing task to SFP/SC insertion in any published RL paper. If the architecture works on USB, it probably works on us.
- **F/T-native.** End-effector wrenches feed the SAC critic and policy by design. No bolt-on.
- **Demonstrated sub-mm precision.** RAM/SSD insertion is essentially zero-tolerance and HIL-SERL clears it.
- **Strong sample efficiency.** 20–30 demos + 20–50k online steps for full convergence. We can run that in a day on one desktop.
- **Architecturally portable.** Although the paper is real-only, the stack (RLPD core + impedance control + ResNet image encoder + wrist F/T + binary success classifier from teleop) ports to Isaac Lab / Gazebo with minimal change.
- **Reward classifier** (binary success detector from a small set of labeled trajectories) sidesteps the reward-shaping nightmare for contact-rich tasks.

## Why this could fail for AIC (skeptical)

- **Human-in-loop, by name.** The published method literally has a human pressing intervention buttons during training. Our team is one person; HIL throughput is bounded by operator hours. **Mitigation**: use **scripted "human" interventions** from CheatCode (file `01`). This is no longer HIL strictly — it's "Scripted-Expert-in-Loop SERL" — but the algorithmic stack is unchanged.
- **Sim-to-eval is sim-to-sim.** The paper is real-only. We'd train in Gazebo and eval in Gazebo, but the sim physics may differ from what HIL-SERL implicitly relies on. Less risky than sim-to-real, but not zero.
- **No LeRobot integration.** Implementation cost: 1-2 person-weeks to port the SERL repo onto our Observation / `aic_controller` plumbing. We're not using JAX in pixi by default; the SERL stack is JAX-native.
- **Reward classifier needs labeled successes.** ~100 labeled "success" / "fail" snapshots. Cheap to generate via CheatCode + ground-truth.
- **Sub-mm precision claim is on a *specific* real connector**; not the same as **randomized board pose + 5 NIC indices + 2 plug types**. We need to test that the same algorithm handles distributional variation.

## Generalization analysis

| Axis | Generalizes? | Notes |
|---|---|---|
| NIC index 0–4 | strong with diverse training | Image-based perception via ResNet-10; randomize the board pose during training. |
| Board pose & yaw | strong | Same. |
| Plug type (SFP/SC) | moderate; needs explicit conditioning | Task one-hot or text input. |
| Grasp-pose noise | **strong** | RL with F/T can actively react. This is the headline strength. |
| Lighting / texture | moderate w/ image aug | Standard image augmentation in the RLPD stack helps. |
| Sim-to-eval | moderate-strong | Smaller gap than sim-to-real. Aggressive DR still recommended. |

## How HIL-SERL works (architectural sketch)

1. **Bootstrap with demos**. ~20-30 teleop demos (we substitute scripted CheatCode trajectories).
2. **Train a binary reward classifier** (CNN on the last-frame observation) from labeled successful/failed terminal states. ~100 labels.
3. **Run RLPD online**:
   - Off-policy SAC with Q-ensembling (5-10 critics).
   - Replay buffer: 50% from demos + 50% from on-policy rollouts.
   - High UTD (update-to-data ratio) ~ 5-10.
   - Layer norm everywhere; standard image augmentation (random crop + color jitter).
   - Observation: stacked recent images (3 cameras) + F/T (3-step history) + joint state + TCP pose.
   - Action: Cartesian impedance command (delta in `gripper/tcp` frame).
4. **Intervention budget**: ~5-10% of rollouts feature a human (or scripted) intervention to demonstrate the recovery.
5. **Termination**: reward classifier fires "success" → episode ends, reward = +1.

## Key resources

| Resource | Year | What |
|---|---|---|
| Luo et al., "Precise and Dexterous Robotic Manipulation via HIL-RL", Science Robotics 2025 | 2024-25 | arXiv 2410.21845 |
| **rail-berkeley/hil-serl** | maintained | <https://github.com/rail-berkeley/hil-serl> — JAX, CUDA 12, Python 3.10. ROS-based real-robot infra; we'd port the algorithm core. |
| **rail-berkeley/serl** | maintained | <https://github.com/rail-berkeley/serl> — the non-HIL precursor; arguably more directly applicable for us (we're "scripted-expert" not "human-expert"). |
| Ball et al., "RLPD" | 2023 | arXiv 2302.02948. <https://github.com/ikostrikov/rlpd> — core algorithm. |
| Karaev et al., "ResiP" / "From Imitation to Refinement" | 2024 | arXiv 2407.16677 — residual RL story that complements HIL-SERL. |
| LeRobot HIL-SERL workflow guide | maintained | A community-contributed guide exists; not first-class. |

## Data needs

- **Type**: (a) demonstrations to bootstrap, (b) reward classifier labels (binary success on terminal states), (c) online RL rollouts during training.
- **Amount**:
  - Demos: 20-30 scripted/CheatCode trajectories (per plug type).
  - Reward labels: 100-200 labeled terminal states.
  - Online rollouts: 20-50k env steps total per training run.
- **Distribution requirements**: cover the full eval-time randomization (all 5 NIC indices, both plug types, board pose range).
- **Collection strategy**:
  - Demos: [`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md) — same pipeline. Tiny slice.
  - Reward labels: a few hundred labeled snapshots from the same dataset. **Cheap to auto-generate** by reading `scoring.yaml` Tier 3 for ground-truth labels.
  - Online: [`../10_data/05_online_gazebo_auto.md`](../10_data/05_online_gazebo_auto.md) — headless Gazebo episode loop driven by the RL trainer.
- **Overlap**: bootstrap demos overlap with [[il-act]], [[il-diffusion-policy]], [[il-force-aware]]. Online stage uses unique infrastructure but the data is throwaway.

## Compute & time

- **Demos collection**: ~1 hour (~30 episodes × 1 min/episode).
- **Reward classifier training**: ~15 minutes (small CNN on 100-200 labels).
- **Online RL**: ~2-3 hours wall-clock for 30k steps in Gazebo at 1.0 RTF. **Doubles if Gazebo RTF drops to 0.5.** Headless mode + GI off + parallel Gazebo instances can compress this.
- **Total per policy**: ~4-6 hours wall-clock per training run.
- **Inference**: small ResNet-10 + small SAC actor → ~5 ms / step. Easy.
- **VRAM**: 16 GB fits comfortably (ensemble of 5-10 small critics + ResNet-10).

## Best simulation environment

**Gazebo** — eval-native, F/T model matches. The HIL-SERL paper is real-only so they don't have a sim bias. For us, training in eval-sim is the cleanest sim-to-eval bridge.

**MuJoCo** as a complementary regression check: train a sister policy in MuJoCo with the same recipe, verify it still works, gain confidence in the *algorithm* (not just the simulator-specific reward shaping).

## Auto-research applicability

**Medium fit.**

Tunable axes:
- UTD ratio (1-10)
- Demo:online sampling ratio (25/75 to 75/25)
- Critic ensemble size (3-10)
- Image augmentation strength
- F/T history length
- Reward classifier threshold
- Intervention frequency (if using scripted expert)

Iteration cost: 4-6 hour training per config + 30 min eval = ~5 hour iter. Smaller per-day count than IL. Karpathy fit: **medium** — slower per iter; better suited to overnight batches of 3-4 configs than rapid sweeps.

## My note: top-30 probability — **high**

This is the single method with the strongest published evidence of working at our task scale and tolerance. **If we can port the algorithm core to Gazebo without subtle bugs**, expected Tier 3 is 65-80 per trial × 3 = **200-240, plus Tier 2** → ~250-300 total. Top-30 likely.

**Risk factors**:
- Engineering cost of porting JAX-native SERL to our pixi env. Could spend a week on plumbing alone.
- The "scripted-expert" variant (no human) may underperform; published gain came from human interventions catching corner cases.
- Gazebo training instability (RTF drift, controller resets) eats into online steps' value.

**Path to top-30**:
1. Port SERL (not HIL-SERL specifically) into our toolkit. Reward classifier + RLPD + Gazebo integration.
2. Bootstrap with ~30 CheatCode demos.
3. Train online for ~30k steps in headless Gazebo.
4. If plateau, swap in scripted interventions (CheatCode steps in for the last 10% of failed episodes).

## Priority for our project — **2 of 5**

- Strongest theoretical fit; biggest engineering cost.
- Best deployed AFTER an IL baseline (file `06` F/T-aware ACT) is up — RL refinement on top of a working IL warm start is the proven path (ResiP-style).
- Could be primary if we have engineering time. As a secondary refinement layer, lower risk.

## Cross-refs

- Algorithmic core: [[rl-residual]] (file `10`) — residual RL closes the same gap structurally.
- Bootstrapping data: [[offline-scripted-groundtruth]] ([`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md)).
- Online rollouts infrastructure: [[online-gazebo-auto]] ([`../10_data/05_online_gazebo_auto.md`](../10_data/05_online_gazebo_auto.md)).
- Demo-bootstrap family: [[hybrid-demo-rl]] (file `22`).
- Force-aware IL precursor: [[il-force-aware]] (file `06`) — pretrain stage before this RL stage.
- Pairs naturally with [[repr-pretrained]] (file `18`) frozen DINOv2 features instead of training the ResNet-10 from scratch.
