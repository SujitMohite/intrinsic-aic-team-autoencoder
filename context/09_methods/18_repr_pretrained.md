# Pretrained Vision Encoders — R3M, VC-1, VIP, Voltron, DINOv2, Theia

## TL;DR

Skip training your own encoder. Use a **frozen pretrained vision backbone** that someone already trained on millions of robot-or-natural-image hours. Feed its features into a small policy head. For manipulation specifically, **R3M, VC-1, and VIP** were trained for robot-control tasks; **DINOv2** and **Theia** are strong generalist self-supervised vision foundations. Each gives a ~512-2048-dim feature per image. Often **beats from-scratch encoders on downstream control** with 10× less compute and 100× less data.

## Why this could work for AIC

- **Zero pretraining cost.** Download weights, run inference. We save the entire AE-pretraining effort of file `17`.
- **Strong visual generalization out-of-the-box.** DINOv2 features are remarkably invariant to lighting, texture, and viewpoint.
- **Small policy head needed.** Once features are 512-dim, a 3-layer MLP can ride on top. Massively reduces our policy's data requirement.
- **Robot-specific encoders (R3M, VC-1, VIP) include temporal / language supervision** that helps with manipulation specifically.
- **Inference is cheap when batched across cameras.**

## Why this could fail for AIC (skeptical)

- **Frozen features may miss the 5 mm port.** Pretrained encoders care about object identity, not sub-cm spatial detail. **The port is a small visual feature** in a 256×256 image; pretrained encoders may pool over it.
- **Trained on real-world images.** Gazebo's renders look different — fewer textures, fixed lighting (with GI). Pretrained features can be brittle to that distribution shift.
- **R3M / VC-1 outputs lack spatial structure.** They're global pool features. We lose pixel-level spatial info, which matters for visual servoing. Use intermediate spatial features (e.g. DINOv2 patch tokens) instead of pooled vectors.
- **Updating the backbone (LoRA / partial unfreeze) helps but costs VRAM.** Then we're closer to training-an-encoder than to frozen-features.

## Generalization analysis

| Axis | Generalizes? | Notes |
|---|---|---|
| NIC index 0–4 | strong | Backbone doesn't care about identity at this resolution. |
| Board pose & yaw | strong | Excellent — that's what pretrained encoders are good at. |
| Plug type | weak | Backbone may not distinguish SFP from SC at small scale. Add ground-truth-driven aux head if needed. |
| Grasp-pose noise | strong | Robust. |
| Lighting / texture | strong | The headline strength. |
| Sim-to-real | strong (DINOv2 / Theia) | The single best lever we have for Phase 2 transfer. |

## Candidate encoders

| Encoder | Pretrained on | Output | License | URL |
|---|---|---|---|---|
| **R3M** | Ego4D + manipulation tasks | 2048-D global pool | MIT | <https://github.com/facebookresearch/r3m> |
| **VC-1** | Ego4D, ImageNet, ManiSkill, etc. ("CortexBench") | 768-D ViT feature | MIT | <https://github.com/facebookresearch/eai-vc> |
| **VIP** | Value-implicit pre-training on robotic video | 1024-D | MIT | <https://github.com/facebookresearch/vip> |
| **Voltron** | Language-conditioned reps | 384-D | MIT | <https://github.com/siddk/voltron-robotics> |
| **DINOv2** | LVD-142M (Meta's curated natural images) | 384–1536-D patch tokens | Apache 2.0 | <https://github.com/facebookresearch/dinov2> |
| **Theia** | Multi-foundation distillation (DINOv2 + SAM + CLIP) | 1024-D | MIT | <https://github.com/bdaiinstitute/theia> |
| CLIP / SigLIP | Image-text pairs | 512–768-D | OpenAI / Google | various |

For AIC, the strong picks are **DINOv2** (best general visual features), **Theia** (distilled multi-foundation; specifically targets robotics), and **R3M** (manipulation-flavored). I'd run all three frozen and compare downstream BC on a small held-out split. The decision data is one afternoon of compute.

## Architecture pattern

```
[3 cams]  → DINOv2 (frozen) → 3 × patch tokens (e.g. 196 × 384)
                          → spatial pool / cross-attention pool → 3 × 384
[F/T, joints, TCP, task] → small MLP → 64
                                       concat
                                       ↓
                                       Policy head (ACT / Diffusion / MLP)
```

Key choices:
- **Pool the patch tokens, don't just take CLS.** Manipulation needs spatial information. Cross-attention pool or simple spatial-mean of a subset of tokens.
- **Keep backbone frozen for first round.** Unfreeze with LoRA (rank 8-16) if downstream eval plateaus.
- **Don't downsample images aggressively** before the encoder — DINOv2 is trained on 224x224 or 518x518 at best.

## Key resources

| Resource | Year | What |
|---|---|---|
| Nair et al., "R3M: A Universal Visual Representation for Robot Manipulation" | 2022 | arxiv: 2203.12601 |
| Majumdar et al., "Where are we in the search for an artificial visual cortex for embodied intelligence?" (VC-1) | 2023 | arxiv: 2303.18240 |
| Ma et al., "VIP: Towards Universal Visual Reward and Representation via Value-Implicit Pretraining" | 2022 | arxiv: 2210.00030 |
| Karamcheti et al., "Voltron: Language-Driven Representation Learning for Robotics" | 2023 | arxiv: 2302.12766 |
| Oquab et al., "DINOv2: Learning Robust Visual Features without Supervision" | 2023 | arxiv: 2304.07193 |
| Shang et al., "Theia: Distilling Diverse Vision Foundation Models for Robot Learning" | 2024 | arxiv: 2407.20179 |
| **LeRobot integration**: most LeRobot policies accept a `vision_backbone` arg | maintained | Drop-in DINOv2 / ResNet via timm |

## Data needs

- **For the encoder**: NONE. It's pretrained.
- **For the downstream head**: same as whatever method you put on top (BC, ACT, Diffusion).
- **Optional**: if we unfreeze with LoRA, we need ~1k–10k images of OUR distribution to align the backbone to Gazebo. Available for free from [`../10_data/07_self_supervised_obs.md`](../10_data/07_self_supervised_obs.md).

## Compute & time

- **Inference (DINOv2-base, 224×224)**: ~15-20 ms per image on RTX 2000 Ada. Three cameras → 45-60 ms total. **Borderline for 20 Hz.** Mitigations: use DINOv2-small (~5 ms), process every other frame, or share trunk across cameras.
- **DINOv2-small (~22M params)**: comfortably real-time.
- **Theia**: distilled to be smaller; check the released checkpoint sizes. ~30-50M params expected.
- **Optional LoRA fine-tune**: 1-2 hours on the desktop. Fits in 16 GB.

## Best simulation environment

**Agnostic.** Pretrained encoders care less about the simulator's specific look than learned ones. Gazebo data fine for training; if we worry about lighting / texture, mix in Isaac / MuJoCo renders.

## Auto-research applicability

**Medium fit.**

Tunable axes:
- Which backbone (DINOv2-S/B/L, Theia, R3M, VC-1)
- Frozen vs LoRA-unfrozen
- Pooling strategy (CLS / mean / cross-attention / spatial keep)
- Patch granularity (which DINOv2 size)
- LoRA rank
- Optional aux finetune on our self-supervised data

Iteration is fast because we don't retrain the backbone: just train the head (1-3 hours) + eval (30 min) → ~4 hour iter. ~5/day. Karpathy fit: **medium** — the encoder choice has discrete options (~6 backbones) which is small for LLM-driven search, but the LoRA tuning is more tractable.

## My note: top-30 probability — **n/a standalone; high paired**

As with [[repr-autoencoder]] (file `17`), this is a force-multiplier. The question is: **does a pretrained encoder beat our team-autoencoder on downstream control?**

My honest expectation: **frozen DINOv2 patch tokens + a small policy head will beat a from-scratch β-VAE + the same head** in 7/10 cases on a randomized manipulation task in sim. The pretrained encoder has seen more visual variance than we can collect in months.

**The team-autoencoder identity is at risk here.** Worth surfacing: maybe "team-autoencoder" should rebrand internally as "team-representation-learning" — meaning we systematically explore the latent-front-end space, of which from-scratch AE is one option among many.

## Priority for our project — **2 of 5**

- **Build it as the immediate baseline encoder** for ACT / Diffusion / BC.
- **A/B vs from-scratch AE.** This is the experiment that decides whether "team-autoencoder" the brand survives "team-pretrained-encoder" the result.
- Operational caveat: download backbones to local cache; bake into the submission Docker image (the eval cloud may not have network egress).

## Cross-refs

- Direct competitor: [[repr-autoencoder]] (file `17`).
- Direct competitor (self-sup masked): [[repr-mae]] (file `19`).
- Feeds: [[il-bc]], [[il-act]], [[il-diffusion-policy]], [[il-vqbet]], [[il-force-aware]], [[il-3d]], [[rl-residual]], [[rl-hil-serl]], [[hybrid-classical-learned]].
- Optional LoRA data → [[self-supervised-obs]] ([`../10_data/07_self_supervised_obs.md`](../10_data/07_self_supervised_obs.md)).
