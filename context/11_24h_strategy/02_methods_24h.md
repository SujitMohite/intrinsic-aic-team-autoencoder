# 24-Hour Method / Policy Strategy

> **Honest top-30 probability with this plan: ~25%.** Best case 30%, worst case 10%. Top-50 ~50%. Valid submission ~85%. This is a stretch goal, not a base case. Read "Critical pushback" before committing.

Companion: [`./01_data_24h.md`](./01_data_24h.md). Long-form reference: [`../09_methods/`](../09_methods/).

## TL;DR

Single primary track: **F/T-conditioned ACT** with **frozen DINOv2 visual front-end**, trained on the keystone data pipeline + aggressive synthetic DR. Auto-research loop sweeps a small shortlist of (chunk size, F/T concat, DR strength, demo subset) configs sequentially on the single GPU. **Classical hybrid fallback** (port detector + impedance FSM) is built as a parallel side-task by Codex on the assumption it has enough autonomy — if not, drop it. Skip all VLAs, all RL, all 3D, all from-scratch encoders. Submit the better of {best F/T-ACT, classical fallback} at hour 22.

## What we're picking and why

### Primary: F/T-ACT + frozen DINOv2

Why this exact combo (not something simpler, not something fancier):

| Component | Why this one |
|---|---|
| **ACT (action chunking transformer)** as the policy class | LeRobot first-class. ~6-8 hours training time. Published 80-90% success on bi-manual fine manipulation (cable-threading-class). Handles short-horizon multi-step actions natively. |
| **F/T concatenation in state vector** (Bi-ACT style) | +12-33 percentage points across the force-aware IL cluster (FoAR / ForceVLA / ManipForce / Bi-ACT). ~50 lines of code on top of vanilla ACT. **Best single ROI in our list.** |
| **Frozen DINOv2-Small** (no fine-tune) | Saves 6-12 hours of from-scratch encoder training. Skips the team-autoencoder pretraining step entirely. DINOv2 spatial tokens > pooled features for manipulation. Inference ~5 ms / image. |
| **Task conditioning via one-hot** {plug_type, port_name} | Explicit goal signal. The VAE z in ACT can't be relied on to disambiguate SFP vs SC; explicit conditioning does it cleanly. |
| **Aggressive synthetic DR in dataloader** | Free multiplier. Visual + F/T noise + JPEG aug. Compensates for thin continuous-axis data coverage. |
| **RTC (Real-Time Chunking) at inference** | Hides ACT's ~10-20 ms forward pass behind ongoing chunk execution. Effectively zero perceived latency. LeRobot supports it. |

**Why not pure ACT (skip the F/T)?** Loses ~20pp. The F/T extension is a $20 bill on the sidewalk — pick it up.

**Why not Diffusion Policy?** Longer training (6-12 hr vs 4-6 hr for ACT). Inference latency tighter. Marginal published gain over ACT at our data scale. In 48 hours: run both. In 24: pick ACT.

**Why not VLA fine-tune (SmolVLA / π0 LoRA)?** Two reasons:
1. LoRA debugging on a 16 GB card with our specific obs schema is multiple hours of integration work.
2. The pretrained VLA's prior is on coarse manipulation; the cross-embodiment data didn't include sub-cm insertion. Marginal-to-no gain vs ACT in 24h on our task class.

**Why not the from-scratch team-autoencoder?** Same critique: pretraining the AE eats 4-8 hours that would otherwise go to policy training. Frozen DINOv2 dominates from-scratch AE at our data scale. **Honest version: the team-autoencoder identity is on hold for 24h.**

### Fallback: Classical hybrid (port detector + impedance FSM)

What and when to run it:

| Component | Detail |
|---|---|
| Port detector | Frozen DINOv2 + small head on auto-labeled crops (CheatCode ground-truth bounding boxes). ~1-2 GPU-hours to train. |
| Classical FSM | APPROACH → ALIGN → SEARCH → SETTLE state machine with per-state impedance tuning. |
| F/T sensing | Trigger SEARCH → SETTLE on edge-contact force spike. |

**Time budget**: ~6-8 person-hours total. Probably needs to run during off-GPU windows or as a Codex-driven parallel task.

**Decision rule**: at hour 20, eval both tracks against a 50-trial Gazebo regression set. Submit whichever scores higher. If F/T-ACT cleared Tier 1 and got > 30 Tier-3 per trial, ship it. If not, ship classical.

**Honest version**: the fallback exists primarily so we have a Tier-1-pass submission even if learning fails. It probably scores worse than F/T-ACT in the best case, but it's a non-zero floor.

## Methods we skip in 24h (and why each is rejected)

| Method | Skip reason | When to revisit |
|---|---|---|
| Vanilla BC (file `02`) | Compounding error: ~5% on sub-cm at 50 demos. Even at 1500 demos, plateaus far below ACT. | Never — strictly dominated by ACT. |
| Diffusion Policy (file `04`) | Marginal gain over ACT in 24h. Longer training. | 48h+ as parallel bet. |
| VQ-BeT (file `05`) | Fast but unproven on sub-cm. | 48h+. |
| 3D-IL family (file `07`) | Requires depth pipeline. ~1 day engineering for Gazebo depth. | When we have time to add depth. |
| SE(3)-equivariant (file `08`) | Specialized arch. Slow forward pass. Few practitioners. | Never for this competition. |
| RL: PPO + Isaac (file `09`) | 24-48 h training MINIMUM. Doesn't fit in 24h. | If IL plateaus + we have weeks. |
| Residual RL (file `10`) | Needs working base + reward + many hours of online RL. | After IL works. |
| World models (file `11`) | Speculative. No published sub-cm result. | Probably never. |
| HIL-SERL (file `12`) | Closest published analog, BUT engineering port from JAX SERL is multi-day. | If we got 48-72h. |
| OpenVLA (file `13`) | Skipped permanently — needs 24 GB minimum for FT. | Never on our hardware. |
| Octo (file `14`) | Superseded by π0 / SmolVLA. | Sanity-check only. |
| SmolVLA / π0 (file `15`) | LoRA debugging eats time; gain over F/T-ACT unclear at small data. | 48h+ if curious. |
| GR00T / Helix / Gemini (file `16`) | Humanoid-centric / closed / partner-only. | Never. |
| From-scratch AE (file `17`) | Frozen DINOv2 dominates at our data scale. | Phase 1 with more time. |
| MAE (file `19`) | Same as AE. | Phase 1. |
| LLM-planner (file `20`) | Wrong tool — we have one skill, not a multi-step plan. | Never. |
| Hybrid demo-RL (file `22`) | RL component too slow for 24h. | After IL works. |

That leaves: **F/T-ACT (primary)** + **classical hybrid (fallback)**. Two tracks, one shippable winner.

## Critical pushback on "simple scales" at the 24h method scale

(Same theme as the data-side critique, applied to model choice.)

Your intuition: simple wins at scale.

**Where it applies, and we use it**:
- **Single primary track.** Don't run 5 parallel methods. One careful F/T-ACT > five half-baked variants. We're choosing "simple" in the project-management sense.
- **Frozen encoder, not learned.** DINOv2 frozen is conceptually simpler than co-training an encoder with the policy. Use it.
- **Skip the team-autoencoder for now.** From-scratch self-supervised pretraining is more "moving parts" than frozen pretrained, not less.

**Where it doesn't apply, and we diverge**:
- **Architectural priors that beat data scaling at small data.** F/T concat (+20pp), action chunking (~10× compounding-error reduction), frozen DINOv2 (~1B-image visual prior) — each is a complexity bump that yields more than 100× the equivalent data needed to match it. At 24h we're priors-dominated, not data-dominated.
- **Hyperparameter precision.** A wrong LR or chunk size at our scale costs 30-50% of performance. "Just use defaults" loses. The auto-research loop has to actually tune.

**Net**: **architectural complexity high, project-management complexity low.** One model with strong priors, swept narrowly. Not many models swept widely.

## The "parallel training via auto-research loop" — what it actually is at 24h

**Honest framing: this is sequential training with an automated config picker, not parallel training.**

We have **one GPU**. Two training runs cannot share it productively. What we can do:

```
GPU timeline (24 hr):

| 0h-2h | 2-6h | 6-10h | 10-11h | 11-15h | 15-19h | 19-22h | 22-24h |
| build | idle | train | eval   | train  | train  | eval+  | submit |
|       |      | v1    | v1     | v2     | v3     | tune   |        |
| pipe  | data | (4hr) |        | (4hr)  | (4hr)  |        |        |
```

Auto-research's actual role in 24h: at hours 10, 15, 19 — Codex picks the **next config** from a fixed shortlist using the previous metrics. **It does not invent configs**; it **selects from a small enumerated set** (see below). Sequential = 3-4 training runs total in 24h.

### What Codex orchestrates in 24h

```
shortlist.yaml — fixed at hour 0:

configs:
  - id: v1_baseline
    encoder: dinov2-small-frozen
    chunk_size: 16
    ft_concat: true
    dr_strength: medium
    demo_subset: all

  - id: v2_more_dr
    same as v1 but dr_strength: aggressive

  - id: v3_smaller_chunk
    same as v1 but chunk_size: 8

  - id: v4_bigger_chunk
    same as v1 but chunk_size: 32

  - id: v5_resnet_encoder
    encoder: resnet-18 (trained)
    ...

  - id: v6_no_ft
    same as v1 but ft_concat: false  (ablation)

  - id: v7_demo_balanced
    same as v1 but demo_subset: balanced (per-NIC equal sampling)
```

Codex picks v1 first (most likely winner per prior research). After v1 evals, picks v2 or v3 based on:
- If v1 plateaus → try v3 / v4 (chunk size)
- If v1 has high variance across NIC → try v7 (balanced sampling)
- If v1 fails on grasp-noise → try v2 (more DR)

That's a **decision tree, not a search**. We give it the tree at hour 0. Codex executes it.

**What Codex does NOT do in 24h**:
- Invent new architectures.
- Modify the eval harness.
- Run more than ~4 training runs (because GPU time is the bottleneck, not LLM cost).
- LLM-as-judge anything.

This is far from full Karpathy autoresearch (see [`../10_data/12_auto_research_loop.md`](../10_data/12_auto_research_loop.md)). In 24h we can't afford the iteration count autoresearch needs to find signal.

## Detailed hour-by-hour training schedule

```
0:00 - 2:00    Stand up:
                 • train_policy.py wrapping LeRobot ACT with custom obs (3 cam + F/T + joints + task one-hot)
                 • Frozen DINOv2-small encoder (downloaded, baked into pixi env)
                 • Synthetic DR transform pipeline
                 • eval_harness.sh (calls headless Gazebo + scoring.yaml summarizer)
                 • shortlist.yaml (the 7 configs above)

2:00 - 6:00    Idle GPU (data collection running on CPU + light GPU).
               Engineering: build classical-hybrid fallback (Codex-assisted port detector).
               Mini-check: train_policy.py runs end-to-end on 50 demos (smoke test).

6:00 - 10:00   Train v1 (ACT + F/T + frozen DINOv2 + medium DR) on the demos available
               (~300-500 at this point). Steps 30k. ~4 hours.

10:00 - 10:30  Eval v1 (5 trials × 3 = 15 trials, scoring.yaml). Codex logs result.

10:30 - 11:00  Codex picks v2 from shortlist using the decision tree.

11:00 - 15:00  Train v2 on the now-larger dataset (~800-1000 demos). 4 hours.

15:00 - 15:30  Eval v2. Codex picks v3.

15:30 - 19:30  Train v3 on ~1200-1500 demos. 4 hours.

19:30 - 20:00  Eval v3.

20:00 - 21:00  Pick winner among {v1, v2, v3}. Run 30-trial regression to confirm.

21:00 - 22:00  Classical fallback eval (30 trials).

22:00 - 23:00  Pick {F/T-ACT winner} vs {classical fallback} — ship whichever scored higher.
               Package as submission container.

23:00 - 24:00  ECR push + portal submission.
```

**Buffer**: ~1-2 hours of slack distributed across the schedule. Used for unexpected debugging.

## Architectural details (the specific F/T-ACT we'd build)

This is what we're building. Specifications are deliberately tight to fit 24h.

### Observation processing

```
per timestep input:
  3 × RGB image, 224×224  (downsampled at observation time)
  6-vec wrist_wrench (F/T)
  6-vec joint_states.position
  6-vec joint_states.velocity
  6-vec controller_state.tcp_pose
  6-vec controller_state.tcp_velocity
  4-vec task_one_hot  [is_sfp, is_sc, is_port_0, is_port_1]

Vision branch:
  3 cams → DINOv2-small (FROZEN) → per-camera (16×16) patch tokens of dim 384
                                  → cross-attention pool → 384-dim per cam
                                  → concat 3 cams → 1152-dim
                                  → linear projection → 256-dim

State branch:
  [F/T, joints, joint_vel, TCP_pose, TCP_vel, task_one_hot]
  → MLP (2 layers) → 256-dim

Concat vision (256) + state (256) → 512-dim obs token
```

### Policy backbone

Standard LeRobot ACT:
- Encoder: 4-layer transformer, dim 512, 8 heads.
- Decoder: 4-layer transformer, dim 512, 8 heads.
- VAE z: 32-dim (KL loss weight 10).
- Action chunk K = 16.
- Action: Cartesian delta (6-vec) in `gripper/tcp` frame + stiffness multiplier (1-vec → applied to default stiffness).

### Loss

```
L = L1(action, target_action) + 10 * KL(z, N(0,I))
```

### Inference

- Chunk K=16 with **temporal ensembling** (mean of last 4 chunk predictions, weighted by recency).
- **RTC**: compute next chunk while current chunk plays out, hide ~15-20 ms forward-pass latency.
- Hold last action if observation arrives with > 100 ms staleness.

### Why these specific defaults

- ACT defaults from the paper, lightly tuned for our 3-cam + F/T obs.
- DINOv2-small not Base — half the params, half the latency, almost the same features for our task.
- K=16 not K=50 — our task is short-horizon insertion, no need for long chunks.
- z=32 not z=64 — small to discourage z from learning to absorb plug-type info (we use explicit conditioning instead).

## Decision criteria at hour 20 (which track ships)

Run a 30-trial regression set (10 SFP trial-1, 10 SFP trial-2, 10 SC trial-3) on each candidate:

| Candidate | Decision |
|---|---|
| F/T-ACT winner: Tier 3 mean ≥ 45 / trial | **Ship F/T-ACT.** Top-30 plausible. |
| F/T-ACT winner: Tier 3 mean 25-45 | Tough call. Ship whichever has higher *total* score (Tier 2 may favor classical's smoothness). |
| F/T-ACT winner: Tier 3 mean < 25 | **Ship classical fallback** if it cleared Tier 1 with positive Tier 3. |
| F/T-ACT failed Tier 1 (validation) | **Ship classical.** No-brainer. |
| Both failed | Ship a stripped CheatCode-WaveArm hybrid that at least passes Tier 1. Floor outcome. |

## Honest top-30 probability bands

| Case | Conditions | Estimated total score | Top-30? |
|---|---|---|---|
| **Best** | F/T-ACT trained on 1500+ demos converges; DR adequate; no surprises | 195-240 | 30-40% |
| **Likely** | F/T-ACT converges but has 1-2 weak NIC indices | 130-180 | 10-20% |
| **Worse** | F/T-ACT plateaus at ~30 Tier-3; classical fallback ships | 100-140 | 5-10% |
| **Worst** | Both fail; floor submission | 50-90 | < 5% |

**Average**: top-30 ~25%. **Median outcome is mid-pack.**

## Critical assessment

Where this plan is fragile:

1. **The keystone pipeline must work by hour 2:30 sharp.** If it slips to hour 5, we lose 2-3 hours of data, which is ~150-300 episodes. Compounds.
2. **F/T-ACT training time is 4 hours per run.** If our LeRobot ACT integration has bugs, debugging eats hours fast.
3. **Frozen DINOv2 must be cached** — eval cloud may not have HF Hub access. Pre-download.
4. **Codex orchestrator must be deterministic and crash-safe.** If it picks a config that crashes mid-training, we lose 4 hours.
5. **Single-GPU contention** between training and eval — solved by sequential scheduling but tight.

What we'd add at 48 hours:
- A second training track (Diffusion Policy with F/T) as a parallel bet.
- Cross-sim DR via Isaac demos.
- More configs in the auto-research shortlist.

What we'd add at 72+ hours:
- HIL-SERL fine-tuning on top of best F/T-ACT.
- Residual RL refinement.
- Multiple seeds per config for variance estimation.

## Cross-refs

- Companion: [[data-24h]] ([`./01_data_24h.md`](./01_data_24h.md)).
- Full-budget method landscape: [[methods-index]] ([`../09_methods/00_index.md`](../09_methods/00_index.md)).
- ACT detail: [[il-act]] ([`../09_methods/03_il_act.md`](../09_methods/03_il_act.md)).
- F/T-aware extension: [[il-force-aware]] ([`../09_methods/06_il_force_aware.md`](../09_methods/06_il_force_aware.md)).
- Frozen pretrained encoder: [[repr-pretrained]] ([`../09_methods/18_repr_pretrained.md`](../09_methods/18_repr_pretrained.md)).
- Classical fallback: [[classical]] ([`../09_methods/01_classical.md`](../09_methods/01_classical.md)) + [[hybrid-classical-learned]] ([`../09_methods/21_hybrid_classical_learned.md`](../09_methods/21_hybrid_classical_learned.md)).
- Full auto-research design: [[auto-research-loop]] ([`../10_data/12_auto_research_loop.md`](../10_data/12_auto_research_loop.md)) — this 24h version is a stripped subset.
- Submission flow: [[06-submission]] ([`../06_submission/00_packaging.md`](../06_submission/00_packaging.md)).
