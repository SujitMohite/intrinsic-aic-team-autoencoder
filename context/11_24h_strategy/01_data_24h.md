# 24-Hour Data Strategy

> **Honest top-30 probability with this plan: ~25%.** Top-50 ~50%. Valid submission ~85%. Numbers below justify this. Read the "Critical pushback" section before committing.

Companion: [`./02_methods_24h.md`](./02_methods_24h.md). Long-form reference: [`../10_data/`](../10_data/).

## TL;DR

Run **one keystone data pipeline** at maximum sustainable throughput for ~20 of the 24 hours: auto-collected scripted-CheatCode demos in headless Gazebo. Target **1500-2000 episodes** covering all 5 NIC indices × 2 plug types. Drop all secondary data strategies (teleop, Isaac, MuJoCo, public datasets, dedicated self-sup obs collection). The dataset feeds the method-side training in pipelined fashion (data growing while training).

## The 24-hour data ceiling

Realistic numbers on our desktop (Xeon + RTX 2000 Ada 16 GB):

| Mode | Throughput | 24h yield |
|---|---|---|
| Gazebo at 1.0 RTF, 1 instance, GUI off, GI on | ~50 ep/h | 1200 |
| Gazebo at 1.0 RTF, 1 instance, GUI off, **GI off**, cameras at 256×256 | ~80 ep/h | 1920 |
| 2-instance multi-Gazebo (RTF degrades to ~0.7) | ~110-130 ep/h aggregate | 2640-3120 |
| 3-instance (RTF ~0.5, physics suspect) | ~150 ep/h | 3600 — **don't trust the cable physics** |

Realistic target accounting for setup time + interruptions + training-GPU contention: **1500-2000 successful episodes**.

This is **NOT "large data"** by any modern standard. Imitation-learning papers with ACT/Diffusion-Policy backbones typically use 50-200 demos and saturate around 1000-5000. We're hitting the lower bound of "enough."

## Critical pushback on the "simple scales" intuition

Your stated intuition: "simple ideas scale better at large data and training."

**True in the limit.** Bitter lesson (Sutton). Pretraining-scale data + raw compute beats hand-designed priors *eventually*.

**Wrong at 24-hour scale, for these specific reasons:**

| The bitter lesson assumes | We have | Conclusion |
|---|---|---|
| Millions to billions of samples | ~1500-2000 episodes (~300k timesteps) | **Off by 100×-1000×** from where simple wins |
| Days to weeks of compute | ~6-12 hours of effective GPU training time | **Off by 10×-50×** from where simple wins |
| Many epochs over diverse curated data | One-shot training pass | Vanilla BC fails at 5% on sub-cm insertion at 50 demos (per IL agent report) |
| Strong noise tolerance | Eval clock is 60 s; one bad mode collapse = 0 score | Compounding error of vanilla BC kills small-data IL |

**Where your intuition DOES apply, and we'll use it**:
- **Data diversity beats data curation.** Don't be clever about which demos to collect — randomize broadly across NIC × plug × pose. Keep it simple on the data sampling axis.
- **Don't over-filter.** Include "close-call" episodes (final position within 5 mm), not just perfect insertions. The model needs the boundary signal.
- **No expensive labels.** F/T + actions + scoring.yaml is enough. No human annotation in the loop.

**Where your intuition does NOT apply, and we'll diverge from it**:
- **Vanilla BC vs ACT at our scale.** Same data, ACT wins by ~10×-20× in success rate at this regime. Architectural priors (action chunking, VAE z) are essentially free wins per engineering hour.
- **From-scratch encoder vs frozen DINOv2.** Frozen DINOv2 has seen ~1B images; we have ~1500 episodes. The pretrained encoder dominates at our data scale and gets simpler with time, not harder. Use it.
- **F/T-conditioning.** +12-33pp success per the force-aware IL cluster. 50 lines of code. Skipping it to "stay simple" is a $20 bill on the sidewalk.

**Net**: stay simple on **data sampling and pipeline plumbing**; spend complexity on **architectural priors that yield large gains per hour**.

## Distribution priorities at 24h scale

Per [`../10_data/09_distribution_design.md`](../10_data/09_distribution_design.md), the full coverage targets need ~5000 demos. We won't hit them. **Compress as follows**:

| Axis | Full target | 24h target | Cost of cutting |
|---|---|---|---|
| Plug type {SFP, SC} | ≥200 each | **300 SFP + 700 SC** | Must have. SC trial is one of three. |
| NIC index 0-4 (in SFP trials) | ≥50 each | **40-60 each** | Must have. Failing one NIC = -20% score. |
| SC port index 0-1 | ≥100 each | **300 each** | Must have. |
| NIC rail translation buckets (5) | ≥20 each | ~8-12 each | Acceptable thin coverage. |
| NIC card yaw offset buckets (3) | ≥30 each | ~13-20 each | Acceptable. |
| Board pose × yaw buckets (12) | ≥30 each | ~3-5 each | **Thin** — board-pose generalization will be the weakness. |
| Grasp-pose noise buckets (9) | ≥50 each | ~10-30 each | Thin. Mitigation: synthetic F/T augmentation. |

**Categorical axes (NIC, plug, port) are well-covered. Continuous axes (rail position, yaw, board pose, grasp noise) are under-sampled.** Mitigate via aggressive synthetic DR ([`../10_data/08_synthetic_dr.md`](../10_data/08_synthetic_dr.md)) in the training dataloader — it's free.

### Sampling order

**Do NOT collect 1000 SFP-NIC-0-yaw-0 episodes then move on.** That's the user's instinct against "clever filtering" — applied wrongly here. Stratified random sampling from the start: every spawned trial picks (NIC, plug, board pose, yaw, grasp noise) independently. After 1500 episodes each marginal axis is well-covered even though most combinations have 0-1 episodes.

## What we skip in 24h (and why)

| Strategy | Skip? | Why |
|---|---|---|
| [[offline-teleop]] (`01`) | ✗ Skip | Manual. Throughput < 30 ep/h. Violates the "automatic" directive. Use only if HIL-SERL becomes the chosen method, which it won't in 24h. |
| [[offline-scripted-groundtruth]] (`02`) | ✓ **Keystone** | The single 24h pipeline. |
| [[offline-public-datasets]] (`03`) | ✗ Skip | Already absorbed by pretrained VLAs. We're not training a VLA. |
| [[online-isaac-parallel]] (`04`) | ✗ Skip | Even with NVIDIA's prepared assets (which we verified exist), Isaac install + Docker + container setup + integration eats 4-6 engineering hours. Net negative in 24h. **In 48h or 72h: include for cross-sim DR.** |
| [[online-gazebo-auto]] (`05`) | ✓ Keep (light) | Use for eval and final regression runs. Don't try to train RL online. |
| [[online-mujoco-sweep]] (`06`) | ✗ Skip | Engineering cost not worth marginal diversity gain in 24h. |
| [[self-supervised-obs]] (`07`) | ✗ Skip standalone | Don't run a dedicated observation-collection process. Pull observation crops from the keystone pipeline as a byproduct if we want AE pretraining (we don't — we use frozen DINOv2 instead). |
| [[synthetic-dr]] (`08`) | ✓ **Free multiplier** | Apply in the training dataloader; near-zero engineering cost. |
| [[distribution-design]] (`09`) | ✓ Reduced version | This file's table above is the compressed version. |
| [[auto-pipeline-design]] (`10`) | ✓ Light version | Build only what's needed — single-sim, single-loop. |
| [[auto-eureka]] (`11`) | ✗ Skip | Eureka is for RL reward design. Not applicable. |
| [[auto-research-loop]] (`12`) | ✓ Stripped version | See companion `02_methods_24h.md` — the 24h variant is sequential config sweep, not full evolutionary loop. |

## Pipeline acceleration tricks

To hit 1500-2000 episodes in ~20 hours of collection, we accelerate the keystone pipeline beyond the default. Each item below is engineering effort vs throughput gain:

| Trick | Effort | Throughput delta |
|---|---|---|
| Disable Gazebo GUI, RViz, plot tools | 5 min | +20% |
| Disable global illumination (`<enabled>false</enabled>` in `aic.sdf`) | 10 min | +30% RTF |
| Downsample camera resolution at recording (256×256 vs 1152×1024) | 30 min | +5% I/O, **major** disk savings |
| Pre-spawn task board once, only re-randomize pose between trials (no full re-spawn) | 1 hr | +25% (skip 10-15 s spawn time per trial) |
| Keep `aic_engine` warm between trials (don't re-launch) | 1 hr | +30% |
| Pre-compile pixi env into a Docker layer | 30 min | One-time setup speedup |
| 2-instance multi-Gazebo (only if RTF stays > 0.6) | 1-2 hr | +60-80% aggregate, **physics risk** |

**Total**: from 50 ep/h baseline → 110-130 ep/h sustained with all accelerations. 20-hour collection window → **2200-2600 episodes**.

**Costs to monitor**:
- RTF drift below 0.5 → physics degrades, F/T traces become noisy. Auto-pause and back off if it happens.
- Multi-instance Zenoh conflicts → use separate Zenoh routers per instance.
- Disk fill → pre-allocate 100 GB. Compress images to JPG q=85.

## Quality gates (realistic for 24h)

Trim from the full quality-gate list in [`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md):

| Gate | 24h check | Action if fails |
|---|---|---|
| Coverage: NIC 0-4 each ≥ 40 demos | After 500, 1000, 1500 episodes | If thin: bias the sampler to under-represented NIC indices |
| Coverage: plug type ≥ 250 each | Same | Same |
| Trial success rate ≥ 85% | Continuous monitoring | If lower: CheatCode-equivalent or engine config has a bug. **Pause and fix.** |
| Action distribution non-degenerate | Histogram on every 500-episode checkpoint | If degenerate: scripted policy has a bug |
| RTF mean ≥ 0.7 across collection | Per-trial RTF log | If lower: drop multi-instance, drop GI further |
| No silent missing F/T data | Sample 10 random trials | If missing: F/T tare bug, fix |

**Skip in 24h**: human inspection of failed episodes, t-SNE on observations, fancy distribution validation. Time we don't have.

## Pipelined integration with training (the "parallel" part)

This is the parallelism story. Honest version: **one GPU = sequential training**. What's actually parallel:

```
Hour 0 ────────────────────────────────────────────────────────── Hour 24
       │
GPU:   ├─[idle]─[train v1]─────[train v2]─────[train v3]─[eval]─[submit]
       │
CPU:   ├─[setup]─[Gazebo headless collection ────────────────]──
       │                       └─ slows when GPU is hot with training
       │
DISK:  ├─[data growing ────────────────────────────────────────]──
       │
Codex: ├─[idle]─[picks v2 config]─[picks v3 config]─[picks v4 from sweep]
```

The data pipeline runs as a **background process** the entire 24 hours. Training pulls dataset snapshots at hour 4, hour 10, hour 16. Each training run sees more data than the last (curriculum from data growth, not from manual scheduling). **Codex orchestrator** picks the next config from a fixed shortlist when each training finishes — that's the auto-research loop's role in 24h.

## What the auto-research loop does to the data side

Almost nothing. **Don't ask Codex to vary data collection parameters in 24h.** Reasons:
- Each data-config change requires restarting collection — wastes hours.
- We don't know which data slice is worth sweeping until we have a baseline model.
- Codex generating bad Gazebo configs (e.g. impossible NIC poses) silently corrupts data.

**Auto-research's data-side scope**: monitor the manifest, flag coverage gaps, suggest bias toward under-represented buckets. That's it. Read-only orchestration on the data side.

## Schedule (hours 0-24)

```
0:00 - 2:00     Build keystone pipeline:
                  • CheatCode launcher script
                  • Headless Gazebo + engine + recorder
                  • Manifest + per-episode parquet writer
                  • All accelerations in place
                Engineering time. Highest-risk hours.

2:00 - 2:30     Smoke test: 10 episodes, validate manifest, confirm scoring.yaml schema.
                If broken: revert, debug, restart. THIS is the make-or-break gate.

2:30 - 6:00     Collection burst phase. Single-instance to keep physics clean.
                Target: 280-320 episodes. Coverage check at hour 6.

6:00 - 22:00    Sustained collection. Add 2nd Gazebo instance if RTF ≥ 0.7.
                Training runs (see `02_methods_24h.md`) interleave at:
                  6:00-10:00 (train v1), 11:00-15:00 (train v2), 15:30-19:30 (train v3).
                During training: collection at reduced parallelism (single instance).
                Between training: full speed.
                Target: 1500-2000 episodes total by hour 22.

22:00 - 23:30   Final eval pass with the chosen model. Package submission container.

23:30 - 24:00   ECR push.
```

## Failure modes specific to 24h

| Failure | Probability | Mitigation |
|---|---|---|
| Pipeline broken at hour 2-3 | Medium-high | Have a fallback: ship `aic_example_policies.ros.WaveArm` clone with renamed class. Tier 1 pass, Tier 3 = 0. Bottom of pack but valid. |
| Gazebo cable softlocks | Medium | Per-trial timeout (60 s) + auto-kill + skip. Pre-build the timeout into the orchestrator. |
| Disk fills | Low if planned | Pre-check 100 GB free. Auto-rotate old episodes if needed. |
| RTF drifts below 0.5 | Medium under multi-instance | Drop to single-instance. Don't fight it. |
| Demos all succeed at the same NIC | Medium if sampler is buggy | Histogram check at hour 6, bias correction at hour 12 if needed. |
| F/T not in obs because of tare bug | Low if scripted | Smoke-test step at hour 2:30 checks for non-zero wrench during contact. |

## Final critical assessment

This data plan is **adequate but not impressive** for top-30 in 24 hours. It collects enough demos to train a credible F/T-ACT, but:

- **Continuous-axis under-coverage** is the dominant generalization risk.
- **No cross-sim DR data** means physics-overfit to Gazebo's specific contact dynamics. Acceptable for Qualification (eval is Gazebo).
- **No teleop / human strategy demos** means the policy has no "expert recovery" patterns. CheatCode is good but not creative.
- **No real way to validate that our distribution matches eval distribution** in advance.

If we had 48 hours, we'd add Isaac cross-sim DR (file [`../10_data/04_online_isaac_parallel.md`](../10_data/04_online_isaac_parallel.md)) and double the demo count. The marginal gain in 24h doesn't justify the engineering hit.

## Cross-refs

- Companion: [[methods-24h]] ([`./02_methods_24h.md`](./02_methods_24h.md)).
- Full-budget version: [[data-index]] ([`../10_data/00_index.md`](../10_data/00_index.md)).
- Keystone pipeline detail: [[offline-scripted-groundtruth]] ([`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md)).
- DR multiplier: [[synthetic-dr]] ([`../10_data/08_synthetic_dr.md`](../10_data/08_synthetic_dr.md)).
- Distribution spec: [[distribution-design]] ([`../10_data/09_distribution_design.md`](../10_data/09_distribution_design.md)).
- Pipeline infra: [[auto-pipeline-design]] ([`../10_data/10_auto_pipeline_design.md`](../10_data/10_auto_pipeline_design.md)).
- Full auto-research loop reference: [[auto-research-loop]] ([`../10_data/12_auto_research_loop.md`](../10_data/12_auto_research_loop.md)).
