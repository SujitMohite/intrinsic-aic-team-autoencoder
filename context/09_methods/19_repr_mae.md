# Masked Autoencoder (MAE) + Robot-MAE Variants

## TL;DR

**MAE** (He et al. 2022) is a vision transformer trained with extreme masking (75% of patches) and asymmetric encoder/decoder. The encoder learns rich, spatially-structured representations because it has to "imagine" the missing 75% of the image from the remaining 25%. Compared to vanilla VAE/AE, MAE produces **sharper, more spatially-localized features** and works very well with **ViT backbones**. For robotics specifically, MV-MAE / Voltron / RoboMAE-style variants add multi-view and temporal masking.

## Why this could work for AIC

- **Spatially-structured latent.** Unlike a pooled-CLS VAE, MAE retains per-patch features → useful for spatial tasks like port localization.
- **Self-supervised, image-only.** Zero demos required for the encoder; uses [`../10_data/07_self_supervised_obs.md`](../10_data/07_self_supervised_obs.md).
- **Aligns with the team-autoencoder identity** but with a more modern formulation than vanilla β-VAE.
- **Multi-view extensions** (MV-MAE) naturally handle our 3-camera setup.
- **Excellent pretraining-then-finetune story.** Frozen MAE features feed any policy head; or unfreeze with LoRA for in-distribution alignment.

## Why this could fail for AIC (skeptical)

- **ViT backbones are heavier than ConvNets** at the same accuracy on small images. Inference cost matters for 20 Hz.
- **MAE pretraining is data-hungry.** The original paper used 1.3M ImageNet images. We may have 50k Gazebo images. Pretrained-on-natural-images-then-finetune-on-Gazebo is the practical route, NOT from-scratch MAE on our data.
- **The encoder is image-only.** F/T and joint inputs need a parallel branch (same as DINOv2 / VAE).
- **Reconstruction loss still optimizes pixels, not control-relevant features.** Same critique as VAE.
- **Compared against frozen DINOv2 (file `18`), there's no clear evidence MAE wins on cm-scale manipulation.** A reasonable hypothesis but not a slam dunk.

## Generalization analysis

| Axis | Generalizes? | Notes |
|---|---|---|
| NIC index 0–4 | strong with diverse pretrain data | Spatial-token preservation helps. |
| Board pose & yaw | strong | Same. |
| Plug type | weak (same as VAE) | Add aux supervision. |
| Grasp-pose noise | moderate-strong | Augmentation + spatial tokens help. |
| Lighting / texture | strong if pretrained on natural images + DR | DINOv2 wins on this axis with less work. |
| Sim-to-real | strong (with natural-image pretrain) | The headline pitch for MAE in robotics. |

## Architecture choices

### Vanilla MAE

```
[image 224×224] → 14×14 patch grid → 75% masked → ViT encoder (visible patches only)
                                                  → ViT decoder (with mask tokens) → pixel reconstruction
```

After pretraining: **discard the decoder**; encoder → spatial tokens (196 × 384 for ViT-Small).

### Robot-flavored variants

- **MV-MAE** (multi-view masked autoencoder): mask across all 3 cameras jointly; encoder learns view-consistent features.
- **Temporal MAE**: mask future patches; encoder learns dynamics-aware features.
- **MaskGNN / TAPE**: mask + temporal-attention for video.
- **Voltron**: language-conditioned MAE-style for robotics.

For AIC, **start with vanilla MAE pretrained on natural images** (HuggingFace has `facebook/vit-mae-base`); fine-tune the encoder with low LR on 20k-50k Gazebo images via simple continued MAE pretraining.

## Key resources

| Resource | Year | What |
|---|---|---|
| He et al., "Masked Autoencoders Are Scalable Vision Learners" | 2022 | The MAE paper. arxiv: 2111.06377 |
| Karamcheti et al., "Voltron: Language-Driven Representation Learning for Robotics" | 2023 | MAE + language for manipulation. arxiv: 2302.12766 |
| Seo et al., "Multi-View Masked World Models for Visual Robotic Manipulation" (MV-MWM) | 2023 | MV-MAE in a world-model. arxiv: 2302.02408 |
| Radosavovic et al., "Real-World Robot Learning with Masked Visual Pre-training" | 2023 | MAE pretrain → BC. arxiv: 2210.03109 |
| **HuggingFace `transformers`**: ViTMAEModel | maintained | Reference impl + pretrained weights. |
| **`facebookresearch/mae`** | maintained | Original FAIR code. <https://github.com/facebookresearch/mae> |
| **`facebookresearch/dinov2`** | maintained | DINOv2 is in spirit a competitor; sometimes used as MAE alternative. |

## Data needs

- **For MAE pretraining**: image-only, no labels. Need 50k-500k Gazebo images for in-distribution finetune (after natural-image pretrain). Aim for high visual diversity (DR + multiple NIC indices + lighting variants).
- **Distribution requirements**: maximize coverage; reconstruction loss is most informative on visual variation.
- **Collection strategy**: [`../10_data/07_self_supervised_obs.md`](../10_data/07_self_supervised_obs.md).
- **Overlap**: same observation pool as [[repr-autoencoder]] (file `17`). Building 07_self_supervised serves both.

## Compute & time

- **Continued pretraining of ViT-MAE-Base** on 50k Gazebo images at 224×224: ~6-12 hours on the desktop. Comfortable in 16 GB at batch 64.
- **Inference**: ViT-Small ~5-8 ms / image. ViT-Base ~15-20 ms. Pick S or B based on policy-head latency budget.
- **Downstream head training**: same as any IL head (3-6 hours).
- **Total**: ~1-2 days for a credible MAE-front-end + policy-head pipeline.

## Best simulation environment

**Gazebo for finetune.** Mix Isaac/MuJoCo images if you want broader visual variety for the encoder (helps Phase 2). For Qualification: Gazebo-only is fine.

## Auto-research applicability

**Medium fit.**

Tunable axes:
- ViT size (Tiny / Small / Base)
- Masking ratio (50% / 75% / 90%)
- Pretrain image count
- Linear probe vs LoRA vs full finetune
- Aux loss (port-location supervised head)

Iteration: 6 hr finetune + 1 hr head train + 30 min eval → ~8 hr / iter. Karpathy fit: **medium** — slow per iter; better to batch a few configs and run overnight.

## My note: top-30 probability — **n/a standalone; moderate paired**

MAE is one of three competing pre-trained-encoder options (file `17` from-scratch VAE / file `18` frozen pretrained / file `19` MAE). My intuition:

- DINOv2 (frozen, no training) ≥ MAE (continued pretrain) ≥ from-scratch β-VAE on most manipulation tasks.
- Continued-pretrain MAE *might* edge out DINOv2 if our Gazebo images are sufficiently OOD from natural images.

**This is exactly the experiment auto-research should run**: same downstream policy head, three different front-ends, identical evaluation. The cleanest comparison we can do.

## Priority for our project — **3 of 5**

- Worth implementing if frozen-DINOv2 (file `18`) hits a ceiling on downstream eval.
- Modest setup cost (HuggingFace MAE is ready to import).
- The team-autoencoder brand is **technically more accurate** with MAE than with vanilla VAE — MAE is the modern self-supervised autoencoder.

## Cross-refs

- Direct competitor / sibling: [[repr-autoencoder]] (file `17`), [[repr-pretrained]] (file `18`).
- Feeds: any policy head from the IL/RL families.
- Self-sup data → [[self-supervised-obs]] ([`../10_data/07_self_supervised_obs.md`](../10_data/07_self_supervised_obs.md)).
- Multi-view variant naturally pairs with our 3-camera setup; see "MV-MAE" reference.
