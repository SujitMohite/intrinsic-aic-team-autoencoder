# Methods Index — Team Autoencoder Research

STATUS: living document. Comparison rows + final recommendations will be refined as method files are written. Top of mind: **generalization is the binding constraint**, not algorithmic novelty.

## How to read this folder

Each `NN_<method>.md` file is **independently loadable** — a teammate or agent can pull one file into context without dragging in the rest. The shared template (see `/home/smohite/.claude/plans/keen-honking-scone.md` §Per-method template) ensures comparable structure across methods. Companion folder [`../10_data/`](../10_data/) holds the **data-collection strategies** that feed these methods.

## Files

| # | File | Family | Top-30 prob | Priority | Auto-research fit |
|---|------|--------|-------------|----------|-------------------|
| 01 | [classical.md](./01_classical.md) | Classical | moderate | 4 | low |
| 02 | [il_bc.md](./02_il_bc.md) | IL | low–moderate | 4 | high |
| 03 | [il_act.md](./03_il_act.md) | IL | moderate–high | 2 | high |
| 04 | [il_diffusion_policy.md](./04_il_diffusion_policy.md) | IL | high | 1 | high |
| 05 | [il_vqbet.md](./05_il_vqbet.md) | IL | moderate | 3 | high |
| 06 | [il_force_aware.md](./06_il_force_aware.md) | IL | high | 1 | high |
| 07 | [il_3d.md](./07_il_3d.md) | IL | moderate | 3 | medium |
| 08 | [il_equivariant.md](./08_il_equivariant.md) | IL | moderate | 4 | medium |
| 09 | [rl_ppo_isaac.md](./09_rl_ppo_isaac.md) | RL | low–moderate | 4 | high |
| 10 | [rl_residual.md](./10_rl_residual.md) | RL | moderate–high | 2 | high |
| 11 | [rl_world_models.md](./11_rl_world_models.md) | RL | moderate | 3 | medium |
| 12 | [rl_hil_serl.md](./12_rl_hil_serl.md) | RL | high | 2 | medium |
| 13 | [vla_openvla.md](./13_vla_openvla.md) | VLA | low–moderate | 4 | medium |
| 14 | [vla_octo.md](./14_vla_octo.md) | VLA | low–moderate | 4 | medium |
| 15 | [vla_smolvla_pi0.md](./15_vla_smolvla_pi0.md) | VLA | moderate | 3 | medium |
| 16 | [vla_groot_helix.md](./16_vla_groot_helix.md) | VLA | low | 5 | low |
| 17 | [repr_autoencoder.md](./17_repr_autoencoder.md) | Representation | n/a* | 2 | high |
| 18 | [repr_pretrained.md](./18_repr_pretrained.md) | Representation | n/a* | 2 | medium |
| 19 | [repr_mae.md](./19_repr_mae.md) | Representation | n/a* | 3 | medium |
| 20 | [planner_llm.md](./20_planner_llm.md) | Planner | low | 5 | low |
| 21 | [hybrid_classical_learned.md](./21_hybrid_classical_learned.md) | Hybrid | high | 1 | medium |
| 22 | [hybrid_demo_rl.md](./22_hybrid_demo_rl.md) | Hybrid | high | 2 | high |

`*` Representation-learning methods aren't standalone policies; their top-30 prob depends on the policy head. Counted as "force multipliers" rather than direct candidates.

## My intuitions (stated as intuition, not evidence)

These shape priorities but are **not** commitments. They will be tested as we write each method file and refine numbers from the literature.

1. **Multimodality matters.** The 5-NIC × 2-plug × randomized-board space is genuinely multi-modal in action space. Methods that natively handle multimodality (**Diffusion Policy**, **VQ-BeT**) probably outperform unimodal BC.
2. **F/T sensor is undervalued by generic VLAs.** Cable insertion is fundamentally a contact-force problem. **Force-aware IL** (ForceMimic-style) or any policy with F/T explicitly fed in should outperform pure-vision policies.
3. **Sim-to-eval gap is narrow** because eval *is* Gazebo. We don't need full sim-to-real machinery for Qualification; that budget should go toward **data diversity inside Gazebo** and possibly a smaller bet on cross-sim DR for Phase 2.
4. **Autoencoder alone is a pretraining tool, not a policy.** AE doesn't emit actions. The team-autoencoder name implies a representation; pair with a policy head (BC / Diffusion / Residual RL) to actually compete.
5. **Best automatic data collection = scripted CheatCode + DR in Gazebo.** CheatCode uses ground truth so its rollouts are reliable; sweep it across the full randomization range and we get large supervised demos **without human teleop**. This single pipeline overlaps with ~80% of the methods we'd consider. See [`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md).
6. **Auto-research loop is about combination search**, not algorithm discovery. We're searching the (encoder × policy × data-mix × DR-strength) hypercube. See [`../10_data/12_auto_research_loop.md`](../10_data/12_auto_research_loop.md).
7. **VLAs are tempting but moderate bets.** 16 GB VRAM forces LoRA-only fine-tuning; 5 mm tolerance is below most reported VLA numbers; F/T fusion is bolt-on. Worth one focused attempt with the smallest available checkpoint (SmolVLA or LoRA-OpenVLA), not the primary path.
8. **The cheapest path to top-30 may be hybrid:** classical visual-servo approach to the port + learned 5 mm endgame (residual RL or HIL-SERL fine-tune). It splits the problem on the natural seam (coarse vs. fine) and uses each tool where it's strongest.

## Tentative top-3 path (will be refined after all method files exist)

We'll commit to a primary + 2 backups, not a single bet, because top-30 viability has high variance per method.

### Primary — Diffusion Policy + Force-aware ACT, both fed by the CheatCode keystone pipeline

- Train **Diffusion Policy** (file `04`) and **F/T-conditioned ACT** (file `06`) on the same dataset produced by [`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md) + DR ([`../10_data/08_synthetic_dr.md`](../10_data/08_synthetic_dr.md)).
- Use **autoencoder (file `17`)** as the visual front-end pretrained with [`../10_data/07_self_supervised_obs.md`](../10_data/07_self_supervised_obs.md).
- Reasoning: parallel bets that share ~85% of the data pipeline; we pick the winner empirically.

### Secondary — Hybrid classical → learned residual (files `21` + `10`)

- A scripted visual-servoing approach gets the plug within a few mm of the port.
- A small residual RL or fine-tuned IL head handles the last 5 mm under F/T feedback.
- Reasoning: most reliable path for the "Tier 3 proximity → partial → full" scoring ladder.

### Tertiary — HIL-SERL fine-tune on top of the IL base (file `12`)

- If diffusion / ACT plateau at ~40-point Tier 3, fine-tune online with HIL-SERL using F/T-based success detection.
- Reasoning: the published HIL-SERL paper specifically demonstrates this works on contact-rich insertion at sub-cm tolerance.

## Decision guide

```
Question: Do we have a working scripted CheatCode loop producing demos?
├── No  → BUILD IT FIRST. Without it almost everything else stalls. See ../10_data/02_*.md
└── Yes
    │
    Question: Do successful demos generalize across all 5 NIC indices + both plug types?
    ├── No  → Distribution problem. See ../10_data/09_distribution_design.md
    └── Yes
        │
        Question: What's our VRAM budget for inference?
        ├── < 4 GB  → Stay below 100M params. ACT / DP-CNN ok. Skip VLAs.
        ├── 4-16 GB → DP-Transformer / VQ-BeT / SmolVLA / OpenVLA-LoRA all in.
        └── No constraint → Full OpenVLA fine-tune; but eval cloud caps at 24 GB.
        │
        Question: Do we have a working force-aware policy yet?
        ├── No  → Train F/T-ACT (file 06) FIRST. F/T is our highest-leverage signal.
        └── Yes → Move to multimodal Diffusion Policy.
```

## Cross-walk to data

The companion overlap matrix lives in [`../10_data/00_index.md`](../10_data/00_index.md). Keystone insight: a single auto-collected dataset from CheatCode + DR feeds methods 02, 03, 04, 05, 06, 10, 12, 17, 18, 19, 21, 22 — twelve of our top candidates. Building that pipeline well is the highest-leverage early investment.

## Quick navigation

```
Classical baseline                01
Imitation learning core           02 (BC), 03 (ACT), 04 (Diffusion), 05 (VQ-BeT)
Imitation learning advanced       06 (Force), 07 (3D), 08 (Equivariant)
Reinforcement learning            09 (PPO), 10 (Residual), 11 (World), 12 (HIL-SERL)
Vision-Language-Action            13 (OpenVLA), 14 (Octo), 15 (SmolVLA/π0), 16 (GR00T/Helix)
Representations (force-multipliers) 17 (AE), 18 (Pretrained), 19 (MAE)
Higher-level / niche              20 (LLM-planner)
Hybrids                           21 (Classical+Learned), 22 (Demo+RL)
```

## Update protocol

When new evidence (a successful experiment, a published paper, a hardware reality) changes a top-30 probability or priority, update the table at the top of this file **and** the corresponding method file's "My note: top-30 probability" section. Log the change in [`../07_team/01_decisions_log.md`](../07_team/01_decisions_log.md) so we know why.
