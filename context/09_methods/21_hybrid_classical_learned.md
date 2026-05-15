# Hybrid: Classical Core + Learned Residual / Vision Head

## TL;DR

**Decompose the task on its natural seam.** A hand-engineered classical pipeline handles the **easy 95%** (approach, alignment to within a few mm, contact detection); a small learned head handles the **hard 5%** (the 5 mm endgame with grasp-noise compensation). This is **the cheapest path to top-30 for a small team**: it bounds the learning problem, gives every component a clear contract, and degrades gracefully when any single piece fails. Closely related to [[rl-residual]] (file `10`) but more general — the "learned residual" can be any small neural component (a visual port detector, a learned F/T compliance, or a residual policy), not just RL.

## Why this could work for AIC

- **Splits a hard problem into two easy ones.** Classical handles geometry + impedance (where it's strong). Learning handles perception + force reaction (where classical struggles).
- **Lowest risk on validity (Tier 1).** The classical pipeline can always emit a valid `MotionUpdate`, even if the learned head fails. **No discovery timeout; no dead-air commands.**
- **Engineering reuse.** The port-detector NN reused across methods. The classical impedance setpoint reused across methods. Reuse compounds.
- **Sim-to-real friendly.** Classical components transfer directly to real (impedance is impedance). Only the learned head has a sim-to-real burden.
- **Composable with our other research.** The visual front-end can be our team-autoencoder ([[repr-autoencoder]]); the policy head can be [[il-force-aware]]; the residual can be [[rl-residual]]. **All paths converge on this template.**

## Why this could fail for AIC (skeptical)

- **The "classical part" requires non-trivial engineering**, especially the port detector. If we can't get a robust detector running, the whole hybrid breaks down to learned-only.
- **Splitting points are fuzzy.** "Approach" vs "endgame" is a continuous gradient. We pick a switch criterion (distance threshold, force threshold); wrong threshold causes oscillation.
- **The learned head sees a *different* distribution than end-to-end learning would.** Once classical converges on alignment, the learned head only sees "5 mm endgame" inputs. Distribution-shift risk inside our own pipeline.
- **Engineering load on us is high**: classical pipeline + perception + learned head + state machine + the switch logic. Many moving parts.
- **No single foundational paper to copy.** This is a design pattern, not a method.

## Generalization analysis

| Axis | Generalizes? | Notes |
|---|---|---|
| NIC index 0–4 | strong if port detector is robust | The detector is the single point of failure for generalization. |
| Board pose & yaw | strong | Same. |
| Plug type (SFP/SC) | strong with dual-path | One classical-+-residual stack per plug, or shared with a plug-type switch. |
| Grasp-pose noise | **very strong** | The learned residual is *literally* trained to fix grasp-noise misalignment. |
| Lighting / texture | depends on detector + DR | The detector is the visual robustness piece. |
| Sim-to-real (Phase 2) | best of our candidates | Classical transfers; only residual has to bridge the gap. |

## Architectural pattern

```
                                   FSM controller
                                        ▲
[3 cams] → port detector → port_pose_in_base ─┐
                                              │
[F/T, joints, TCP] ──────────────────────────┼─► classical pipeline → a_base
                                              │
                                              │   (state-machine choice of mode:
                                              │    APPROACH → ALIGN → SEARCH → SETTLE)
                                              ▼
                                       learned residual head (small) ──► Δa
                                              │
                                              ▼
                                  a_final = a_base + Δa
                                              ▼
                                          Robot
```

Three layers:

### 1. Perception: port detector

- **Option A**: YOLOv8n or similar, trained on auto-labeled crops from CheatCode ground-truth.
- **Option B**: Frozen DINOv2 + lightweight head trained on the same labels.
- **Option C**: Learned encoder + heatmap regressor — port location as a 2D peak.

Output: port pose in the camera frame, project to `base_link` via known camera extrinsics.

### 2. Classical pipeline

State machine:
- `APPROACH`: visual servo TCP toward `port_pose_in_base`. Impedance moderate.
- `ALIGN`: when `|xy_err| < 5 mm`, switch to insertion axis-only motion + low stiffness perpendicular.
- `SEARCH`: small spiral / Lissajous; high F/T sensitivity; trigger on edge contact.
- `SETTLE`: drive in along port axis; high z-stiffness, low xy-stiffness.

All using `MotionUpdate` with appropriately tuned `target_stiffness` / `target_damping` / `feedforward_wrench`.

### 3. Learned residual head

Small NN (~5M params) conditioned on:
- F/T history (last 16 samples)
- Current TCP pose error
- Plug type (one-hot)
- Optionally: a small slice of the latent from [[repr-autoencoder]] or [[repr-pretrained]]

Output: 6-vector Cartesian delta, bounded (e.g. ±2 mm, ±0.5°).

Training: BC on demos where CheatCode + classical-base would have errored without correction, OR RL with dense reward (see [[rl-residual]]).

## Key resources

| Resource | Year | What |
|---|---|---|
| Johannink et al., "Residual Reinforcement Learning for Robot Control" | 2018-19 | The foundational paper for the residual pattern. |
| Ankile et al., "From Imitation to Refinement" (ResiP) | 2024 | 5% → 99% via residual on frozen BC; sub-mm. arXiv 2407.16677 |
| Lee et al., "Making Sense of Vision and Touch" | 2019 | Early multimodal fusion + learned residual for contact-rich. |
| Schoettler et al., "Deep RL for Industrial Insertion Tasks with Visual Inputs and Natural Rewards" | 2019 | Hybrid IL+RL for industrial connector insertion. |
| FORGE (Noseworthy 2024-25) | 2024 | Force-threshold conditioning is a hand-engineered hint to a learned head — same philosophy. arXiv 2408.04587 |
| ResiP code: `ankile/robust-rearrangement` | maintained | Reference for the IL-base + residual-RL pattern. |
| HIL-SERL (file `12`) | 2024 | Effectively this pattern with RL+human-in-loop. |

## Data needs

- **Port detector**: 500-2000 auto-labeled crops with bounding boxes from CheatCode rollouts. ★ overlaps with the keystone pipeline.
- **Classical pipeline**: NONE — engineering only.
- **Learned residual**:
  - If trained as IL: (obs, residual_target) pairs. Generated by comparing CheatCode-with-noise trajectories vs. classical-base trajectories.
  - If trained as RL: online rollouts in Gazebo with dense reward.
- **Collection strategy**: [`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md). The keystone dataset gives us both detector labels and residual training targets.

## Compute & time

- **Port detector training**: 1-2 GPU-hours.
- **Classical pipeline tuning**: 1-2 person-weeks of engineering.
- **Learned residual training**: 2-6 hours (BC) or 4-12 hours (residual RL).
- **Inference**: detector ~5 ms + classical ~1 ms + residual ~3 ms = ~10 ms/step. Comfortable for 20 Hz.

## Best simulation environment

**Gazebo for tuning and training**. The classical pipeline must work in eval-sim; the residual must train in eval-sim or with very high-fidelity DR.

## Auto-research applicability

**Medium fit.**

Tunable axes:
- Switch thresholds (xy_err for ALIGN→SEARCH, force for SEARCH→SETTLE)
- Per-state stiffness/damping/wrench
- Spiral parameters
- Residual head architecture and clip magnitude
- Detector backbone / training set size

Mixed loop: classical thresholds are continuous knobs (good for Eureka-style sweeps); residual head training is its own training loop. **Karpathy fit: medium** — multiple sub-loops to manage, but each is well-bounded.

## My note: top-30 probability — **high**

**Best case** (working detector + tight classical + small residual): 70-80 Tier 3 / trial × 3 = 210-240, Tier 2 ~22 each → **280-300 total**. Top-30 strong; possibly top-10.

**Likely case**: 60-70 Tier 3, Tier 2 ~18 → **230-260**. Top-30 plausible.

**Worst case** (detector fails on certain NIC poses): 30-40 / trial → mid-pack on those specific configs.

**Path to top-30**:
1. Build the port detector ([[classical]] file `01` ingredient).
2. Build classical FSM with impedance per state ([[classical]] file `01`).
3. Train F/T-conditioned residual head on data slices where classical fails.
4. Tune switch thresholds via auto-research sweep.
5. Add visual encoder ([[repr-autoencoder]] or [[repr-pretrained]]) as input to the residual head if needed.

**Risk factors**:
- Detector failure on randomized NIC yaw — single point of failure.
- Residual head can be trained on a biased distribution (only seeing endgame); needs careful curation.
- Engineering load: this method has the **most parts** of any in our list.

## Priority for our project — **1 of 5** (tied)

This is the **structurally safest path to top-30**. If a small team has limited bandwidth, the hybrid approach is the highest expected-value method because:
- Validity (Tier 1) is essentially guaranteed.
- The classical part is debuggable.
- Each component fails gracefully.
- Reuses the visual front-end and demo data we'd build anyway.

Run alongside [[il-diffusion-policy]] and [[il-force-aware]] as parallel primary bets. The hybrid is *complementary* to learning-heavy methods — they can each be tested independently against the same eval.

## Cross-refs

- Classical components: [[classical]] (file `01`).
- Residual variants: [[rl-residual]] (file `10`), [[rl-hil-serl]] (file `12`).
- Vision front-end options: [[repr-autoencoder]] (file `17`), [[repr-pretrained]] (file `18`).
- F/T-aware residual head: [[il-force-aware]] (file `06`).
- Data: [[offline-scripted-groundtruth]] ([`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md)).
- Demo-bootstrap RL variant: [[hybrid-demo-rl]] (file `22`).
