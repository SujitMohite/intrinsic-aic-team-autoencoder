# Octo — Berkeley Generalist Transformer Policy

## TL;DR

**Octo** (Ghosh 2024) is a transformer-based diffusion-style policy: 27M (Small) / 93M (Base) params, pretrained on 800k Open X-Embodiment trajectories. Open-source, **fits 16 GB comfortably**, fine-tunes in 2-4 hours on a single consumer GPU. The lightest practical VLA. Outperforms RT-1-X, comparable to RT-2-X-55B on instruction following. **Largely superseded in mindshare by π0 / SmolVLA in 2025**, but remains a credible cheap fallback.

## Why this could work for AIC

- **Lightweight.** Octo-Base fits 16 GB at batch 32 easily.
- **Fast to fine-tune** — 2-4 hours on a single 4070 / RTX 2000 Ada-class GPU.
- **JAX/TPU-friendly** but PyTorch port available.
- **Established baseline** — π0's paper uses it as a comparison baseline.
- **Cheap to try**: if it works at all, we have a working VLA in less than a day.

## Why this could fail for AIC (skeptical)

- **Pretraining at coarse precision.** No sub-cm insertion in OXE.
- **No native F/T fusion.** Bolt-on; same caveat as other VLAs.
- **Superseded by π0 / SmolVLA in published benchmarks.** Both beat Octo on broad manipulation. SmolVLA achieves Octo-class performance with 27M params (vs Octo-Small) or beats Octo-Base at 450M.
- **Less LeRobot integration** than SmolVLA / π0 — not first-class.

## Generalization analysis

Same general profile as SmolVLA / π0 — strong visual generalization from cross-embodiment pretraining.

## Key resources

| Resource | Year | What |
|---|---|---|
| Ghosh et al., "Octo" | 2024 | arXiv 2405.12213. <https://github.com/octo-models/octo> (active, JAX). |
| LeRobot | maintained | Not first-class; importable via JAX. |

## Data needs

- 50-200 demos for FT. Same as π0.
- Collection: [`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md).

## Compute & time

- FT: 2-4 hours on 16 GB.
- Inference: ~15-20 ms per chunk on L4.

## Auto-research applicability — **medium**

Hyperparameter axes similar to π0 but smaller.

## My note: top-30 probability — **low-moderate**

If we're trying a VLA, **prefer SmolVLA** (file `15`). Octo's main use is as a sanity-check baseline — if Octo can't even get proximity, the VLA-for-our-task paradigm is broken.

**Best case**: 40-55 Tier 3 / trial × 3 = 120-165 → mid-pack.

## Priority for our project — **4 of 5**

Try as a one-day sanity check; do not invest beyond that.

## Cross-refs

- LeRobot VLA picks: [[vla-smolvla-pi0]] (file `15`).
- Other VLA options: [[vla-openvla]] (file `13`, skip), [[vla-groot-helix]] (file `16`).
