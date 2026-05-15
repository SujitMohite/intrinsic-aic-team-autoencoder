# Distribution Design — What "Good Distribution" Means for AIC

## TL;DR

**Generalization is the binding constraint** for our score. This file documents the **concrete coverage targets** our training data must hit. Skipping or under-sampling any axis here directly costs points at eval (where that axis is randomized). The keystone CheatCode pipeline can hit these targets automatically — but only if we tell it to.

## The randomization hypercube

The eval engine randomizes:

1. **Plug type** — SFP module or SC plug (2 values).
2. **NIC card index** (in SFP trials) — `nic_card_0` … `nic_card_4` (5 values), each on a specific NIC rail.
3. **NIC rail translation** — continuous, ±~0.022 m (sample config range).
4. **NIC card yaw offset** — continuous, ±~10° (estimated).
5. **SC port index** (in SC trial) — `sc_port_0` or `sc_port_1` (2 values).
6. **SC rail translation** — continuous, ±~0.06 m.
7. **Task board pose** — x, y, z, yaw. Several discrete values × continuous range.
8. **Grasp-pose noise** — ~2 mm translation, ~0.04 rad rotation (per qualification spec).

## Coverage targets

### Categorical axes (must cover every value)

| Axis | Values | Min demos / value |
|---|---|---|
| Plug type | {SFP, SC} | 200 |
| NIC card index (SFP trials) | {0, 1, 2, 3, 4} | 50 |
| SC port index (SC trial) | {0, 1} | 100 |

**Why each minimum:** roughly the demo count needed for ACT / Diffusion Policy to learn a stable mapping on the per-value subset. Below 50, IL methods fail to generalize.

### Continuous axes (must sample buckets)

Discretize into buckets so we can measure coverage.

| Axis | Bucket scheme | Min demos / bucket |
|---|---|---|
| NIC rail translation | 5 buckets of [-0.022, +0.022] m | 20 |
| NIC card yaw offset | 3 buckets of [-10°, +10°] | 30 |
| Task board x | 3 buckets in eval range | 30 |
| Task board y | 3 buckets in eval range | 30 |
| Task board yaw | 4 buckets of [0°, 90°] | 30 |
| Grasp-pose noise translation | 3 buckets of [-2, +2] mm | 50 |
| Grasp-pose noise rotation | 3 buckets of [-0.04, +0.04] rad | 50 |

### Implied dataset size

**Per plug type**, with full bucket coverage:
- 5 NIC × 5 rail × 3 yaw × 3 board-x × 3 board-y × 4 board-yaw × 3 grasp-trans × 3 grasp-rot = ~4000 unique buckets.
- We don't need every bucket combination; we need each axis-bucket marginal to hit min demos.
- **Realistic floor**: 2000 demos per plug type = 4000 total. Realistic stretch: 5000-10000 total.

### How to schedule the sweep

1. **Stratified sampling**: at each iteration, pick a random NIC index, random rail position, random yaw, etc. independently. After N iterations, each marginal axis is well-covered even if no combination is.
2. **Active sampling** (advanced): once we have a working policy, identify under-performing buckets via eval and over-sample those.

## Specific failure modes if we under-cover

| Missed axis | Eval failure mode |
|---|---|
| One NIC index (say 4) | All trials with that NIC fail. ~20% score loss. |
| Edge of NIC rail translation | Off-center placements fail. ~10% score loss. |
| Extreme NIC yaw | Skewed inserts fail. ~10% score loss. |
| Plug type bias (too SFP-heavy) | SC trial collapses. ~33% score loss. |
| Grasp-noise range | Mild perturbations to grasp cause cascading misalignment. ~15% score loss. |
| Board pose | Out-of-distribution boards fail. ~5-15% score loss. |

The cumulative gap between "well-covered training" and "narrow training" is **easily 50+ points** at eval.

## What's already easy to randomize

The Gazebo engine config and `/expand_xacro` already accept randomization params for all of these axes. We just **must** vary them. The default `sample_config.yaml` doesn't.

## What's hard

- **Grasp-pose noise** isn't a launch parameter; it's how the cable attaches in the gripper. We need to inject it into the cable spawn (small random offset in the SDF).
- **Sequencing** — for autoresearch, we want a balanced batch per training session, not all-NIC-0 followed by all-NIC-1. Shuffle.

## Quality gates

Run after data collection:

1. **Per-axis marginal histogram**: each bucket has ≥ min demos.
2. **Per-(plug, NIC) joint coverage**: every SFP × NIC pair has ≥ 30 demos. SC × port has ≥ 60.
3. **Success rate per bucket**: CheatCode should succeed in ≥ 90% of every bucket. If a bucket has high CheatCode failure, it's a sim bug — investigate before training on bad data.

## Cross-refs

- The pipeline that produces this data: [[offline-scripted-groundtruth]] ([`./02_offline_scripted_groundtruth.md`](./02_offline_scripted_groundtruth.md)).
- DR overlay (post-hoc augmentation): [[synthetic-dr]] ([`./08_synthetic_dr.md`](./08_synthetic_dr.md)).
- Auto-research uses this file to inform sweep ranges: [[auto-research-loop]] ([`./12_auto_research_loop.md`](./12_auto_research_loop.md)).
- Every learning method's data section refers back here for the "what we need to cover" spec.
