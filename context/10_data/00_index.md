# Data Strategy Index — Team Autoencoder

STATUS: living document. Overlap matrix + recommendations refined as data files are written.

> **Core thesis** (re-stating the user's framing): the problem isn't algorithmic novelty, it's **collecting data with good distribution** and training the right method on it. **Generalization is the binding constraint**, and we want collection to be **automatic, not manual**.

## How to read this folder

Each `NN_<strategy>.md` file describes one **data-collection strategy** — its outputs, throughput, distribution properties, automation level, and which methods (from [`../09_methods/`](../09_methods/)) it feeds. The companion `09_methods/` folder evaluates the methods; this folder evaluates **how to feed them**.

## Files

| # | File | Type | Automatic? | Throughput | Methods served |
|---|------|------|------------|------------|----------------|
| 01 | [offline_teleop.md](./01_offline_teleop.md) | offline | manual | 10 ep/h | benchmark only |
| 02 | [offline_scripted_groundtruth.md](./02_offline_scripted_groundtruth.md) | offline | **full** | 100+ ep/h | **all IL + AE + RL bootstrap** ★ |
| 03 | [offline_public_datasets.md](./03_offline_public_datasets.md) | offline | full (download) | — | VLA pretrain, representation pretrain |
| 04 | [online_isaac_parallel.md](./04_online_isaac_parallel.md) | online | full | 1000+ ep/h | RL, RL+IL, DR |
| 05 | [online_gazebo_auto.md](./05_online_gazebo_auto.md) | online | full | 50 ep/h | IL fine-tune, RL fine-tune, eval-native DR |
| 06 | [online_mujoco_sweep.md](./06_online_mujoco_sweep.md) | online | full | 200 ep/h | RL (TD-MPC2), cheap experiments |
| 07 | [self_supervised_obs.md](./07_self_supervised_obs.md) | passive | full | 10k img/h | AE, MAE, R3M-style |
| 08 | [synthetic_dr.md](./08_synthetic_dr.md) | augmentation | full | 1× → 10× | all visual policies |
| 09 | [distribution_design.md](./09_distribution_design.md) | meta | — | — | governs all of the above |
| 10 | [auto_pipeline_design.md](./10_auto_pipeline_design.md) | infra | full | — | infrastructure for 02, 04, 05, 06 |
| 11 | [auto_eureka.md](./11_auto_eureka.md) | meta | full | — | RL reward generation |
| 12 | [auto_research_loop.md](./12_auto_research_loop.md) | meta | full | — | **the Karpathy-style end-to-end loop** ★ |

★ = keystone files. Build first.

## Method × Data overlap matrix

`✓` = primary fit (this method needs this data). `o` = optional / nice-to-have. `–` = irrelevant.

Methods abbreviated using the `09_methods/` numbering.

| Method ↓ \ Data → | 01 teleop | 02 scripted | 03 public | 04 Isaac | 05 Gazebo | 06 MuJoCo | 07 self-sup | 08 DR |
|---|---|---|---|---|---|---|---|---|
| 01 Classical | – | – | – | – | – | – | – | – |
| 02 BC | o | ✓ | – | o | o | – | – | ✓ |
| 03 ACT | o | ✓ | o | – | o | – | – | ✓ |
| 04 Diffusion Policy | o | ✓ | o | – | o | – | – | ✓ |
| 05 VQ-BeT | o | ✓ | – | – | o | – | – | ✓ |
| 06 Force-aware IL | o | ✓ | – | – | o | – | – | ✓ |
| 07 3D / DP3 | o | ✓ | – | – | o | – | – | ✓ |
| 08 Equivariant | o | ✓ | – | – | – | – | – | ✓ |
| 09 PPO + Isaac | – | – | – | ✓ | – | – | – | ✓ |
| 10 Residual RL | – | ✓ | – | o | ✓ | – | – | ✓ |
| 11 World models | – | o | – | – | o | ✓ | – | o |
| 12 HIL-SERL | – | ✓ | – | – | ✓ | – | – | ✓ |
| 13 OpenVLA | – | o | ✓ | – | – | – | – | o |
| 14 Octo | – | o | ✓ | – | – | – | – | o |
| 15 SmolVLA / π0 | – | o | ✓ | – | – | – | – | o |
| 16 GR00T / Helix | – | o | ✓ | – | – | – | – | o |
| 17 Autoencoder | – | o | – | – | – | – | ✓ | ✓ |
| 18 Pretrained encoders | – | – | – | – | – | – | – | – |
| 19 MAE | – | o | – | – | – | – | ✓ | ✓ |
| 20 LLM planner | – | – | – | – | – | – | – | – |
| 21 Hybrid classical+learned | – | ✓ | – | – | o | – | – | ✓ |
| 22 Demo-bootstrapped RL | – | ✓ | – | o | ✓ | – | – | ✓ |

### Top-3 keystone data pipelines (what to build first)

Counting columns above, the highest-leverage data strategies are:

1. **`02_offline_scripted_groundtruth.md`** — Auto-collected CheatCode demos.
   - Serves: 02 BC, 03 ACT, 04 Diffusion, 05 VQ-BeT, 06 F/T-IL, 07 3D, 08 Equivariant, 10 Residual RL, 12 HIL-SERL, 17 AE (optional), 19 MAE (optional), 21 Hybrid, 22 Demo-RL.
   - **12+ methods served**. If this pipeline doesn't exist, almost nothing else makes progress.
2. **`08_synthetic_dr.md`** — Domain randomization on top of 02.
   - Serves: every learning method that consumes images.
   - **15+ methods served**. Cheap multiplier on the 02 dataset.
3. **`07_self_supervised_obs.md`** — Unlabeled observations.
   - Serves: 17 AE, 19 MAE, 18 pretrained-encoder fine-tune.
   - The team's stated autoencoder direction depends on this.

### Build order

```
Week 0          02 (scripted CheatCode pipeline)        ← unblocks ~80% of work
Week 0          09 (distribution_design)                ← guides what 02 should cover
Week 0–1        10 (auto_pipeline_design infra)         ← reusable harness
Week 1          08 (synthetic DR)                       ← 10× the value of 02 cheaply
Week 1          07 (self-supervised obs collection)     ← for AE / MAE pretrain
Week 2          05 (online Gazebo auto rollouts)        ← for IL fine-tune / Tier-3 eval
Week 2          12 (auto_research_loop architecture)    ← Karpathy-style harness
Week 3+         04 (Isaac parallel) IF we pursue RL
Week 3+         11 (Eureka for reward gen) IF RL becomes primary
Defer / skip    01 (teleop): manual; only as a benchmark baseline
Defer / skip    06 (MuJoCo): useful as fast regression CI but not data primary
Defer / skip    03 (public datasets): only matters for VLA pretrain, not Qualification
```

## What "good distribution" means here

See [`09_distribution_design.md`](./09_distribution_design.md) for the detailed coverage targets. Summary: **every combination** of {NIC index ∈ 0..4, plug type ∈ {SFP, SC}, board pose buckets, grasp-noise bucket} should have a minimum demo count, with the keystone pipeline (`02`) the primary way of guaranteeing it.

## Pointer into the auto-research loop

The end-to-end design — hypothesis → data slice → train → eval → analyze → next hypothesis — lives in [`12_auto_research_loop.md`](./12_auto_research_loop.md). Eureka-style automated reward generation (relevant only if we pursue RL as primary) lives in [`11_auto_eureka.md`](./11_auto_eureka.md).

## Update protocol

When a method file commits to a specific data strategy, mark the row in the overlap matrix above and bump the "Methods served" count for that data file. When a data pipeline produces a dataset, log the dataset's distribution properties + size + naming convention in the relevant data file's "Storage" section.
