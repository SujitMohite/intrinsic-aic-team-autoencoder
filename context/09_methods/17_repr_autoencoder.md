# Autoencoder (VAE / β-VAE / VQ-VAE) — Representation Learning

## TL;DR

Train a neural autoencoder on wrist-camera images (optionally on multi-modal state) to produce a **compact latent** that a downstream policy head consumes. The autoencoder is **never an action policy on its own** — it's a force-multiplier that improves a policy's sample efficiency, generalization, and inference cost. Three flavors matter for AIC:

- **β-VAE** — continuous Gaussian latent, β tuned for disentanglement / smoothness.
- **VQ-VAE** — discrete codebook latent; pairs naturally with VQ-BeT (file `05`) and tokenized VLAs.
- **Masked autoencoder (MAE)** — see separate file `19`; vision-only self-supervised.

This file focuses on the encoder-decoder family. The team-autoencoder name suggests this is our home base — but read the "Why fail" section: standalone, an AE will not get us to top-30. Paired correctly, it's a strong leg.

## Why this could work for AIC

- **Dimensionality reduction.** A 256×256×3 image is 196k floats; a 64-dim latent is 64. The policy head sees a much smaller input → less data needed → less compute.
- **Visual robustness via reconstruction.** Forcing the encoder to reconstruct teaches it scene structure invariant to specific pixels.
- **Self-supervised.** We can train it on **observation-only data** (no demos required), which means the data pipeline is even cheaper than collecting demos. See [`../10_data/07_self_supervised_obs.md`](../10_data/07_self_supervised_obs.md).
- **Modular.** Same encoder feeds BC / ACT / Diffusion / VQ-BeT / Residual RL. We can swap policy heads without retraining the encoder.
- **Goal-conditioning is easy.** Concatenate a target-port one-hot or text embedding to the latent before the policy head — implicit attention on the target port. The variant the team's `00_approach.md` calls "Variant 2".

## Why this could fail for AIC (skeptical)

- **A reconstruction loss does NOT teach the encoder what matters for control.** Cable insertion needs port location, gripper pose, contact state. Reconstruction optimizes for pixel-level fidelity — uniform background and the robot arm get equal "attention budget" with the port. The encoder may learn beautiful sunsets and miss the 5 mm port.
- **Standalone, AE doesn't emit actions.** Top-30 prob = 0 for a pure AE. Has to pair with a head. Counted here as a force-multiplier.
- **VAE latents collapse easily** if β is too high (posterior collapse) or the policy head is too strong (encoder ignored).
- **The 5 mm tolerance is below typical VAE reconstruction precision** in pixel space. Position-sensitive features get smoothed away in the latent. **Mitigation**: aux losses that supervise port location (when ground truth is available during training).
- **Pretrained encoders (R3M, VC-1, DINOv2) often beat a from-scratch AE** on downstream control — see file `18`. If we can use those, why train our own?
  - Honest answer: we may not need to train our own. The team-autoencoder identity is a *design preference*, not a research result.

## Generalization analysis

| Axis | Generalizes? | Why |
|---|---|---|
| NIC index 0–4 | depends on training data | If self-sup data covers all rails, latent generalizes. If not, fails on unseen rails. |
| Board pose & yaw | depends on training data | Same. DR is mandatory. |
| Plug type (SFP / SC) | weak natively | Reconstruction doesn't care about plug type. Add plug-type-conditioned decoder or contrastive loss. |
| Grasp-pose noise | moderate | Latent is somewhat invariant, especially with augmentation. |
| Lighting variations | strong with DR | The classic strength of AE pretraining. |
| Sim-to-real | weak | Pixel statistics differ. Mix real images in the AE pretrain set when available. |

## Architecture choices

### Backbone

- **CNN (ResNet-18 / ResNet-34 encoder + transposed-conv decoder)**: classical, easy. ~10M params. Fits 256×256 with batch 64 on 16 GB.
- **ViT-Tiny / ViT-Small encoder + MLP decoder for MAE-style** — see file `19`.
- **Conv→VQ→Conv** for VQ-VAE: emits discrete tokens, pairs with tokenized policies.

### Latent dimensionality

- **Continuous**: 64–256 dim usually good for manipulation. Below 32 → posterior collapse risk. Above 512 → policy head becomes the new bottleneck.
- **Discrete (VQ-VAE)**: 256–1024 codebook entries; 4×4 or 8×8 spatial grid → ~16–64 tokens per image.

### Loss

- **β-VAE**: `L = recon_loss + β * KL(q || N(0,I))`. β ∈ [0.5, 4]; start at 1.0. Tune up if latent ignores variation; down if reconstruction is fuzzy.
- **VQ-VAE**: `L = recon + commitment + codebook`. EMA updates for codebook stable.
- **Auxiliary losses (recommended for AIC)**:
  - **Reconstruction-after-future-step** (CURL / next-frame prediction): teaches motion structure.
  - **Port-location prediction** from latent: supervised heatmap regression, ground truth from CheatCode rollouts. **Forces the latent to encode port location.** Crucial.
  - **Plug-type classification** (binary head on latent): cheap auxiliary, ensures plug identity stays in latent.

## Key resources

| Resource | Year | What |
|---|---|---|
| Kingma & Welling, "Auto-Encoding Variational Bayes" | 2013 | VAE foundation. arxiv: 1312.6114 |
| Higgins et al. "β-VAE", ICLR | 2017 | β-VAE for disentanglement. |
| van den Oord et al. "Neural Discrete Representation Learning" | 2017 | VQ-VAE. arxiv: 1711.00937 |
| Razavi et al. "Generating Diverse High-Fidelity Images with VQ-VAE-2" | 2019 | VQ-VAE-2 hierarchical. |
| Yarats et al. "Improving Sample Efficiency in Model-Free RL with a Pixel-Based Decoder" | 2019 | Reconstruction as auxiliary for RL. |
| Laskin et al. "CURL", ICML | 2020 | Contrastive unsupervised reps for RL. arxiv: 2004.04136 |
| Stooke et al. "Decoupling Representation Learning from RL" | 2021 | The pretrain-then-policy pattern. |
| `lucidrains/vq-vae` | maintained | Clean VQ-VAE in PyTorch. <https://github.com/lucidrains/vector-quantize-pytorch> |
| `AntixK/PyTorch-VAE` | maintained | A library of VAE variants. <https://github.com/AntixK/PyTorch-VAE> |
| `Imitation-as-Replay` and other LeRobot examples | maintained | LeRobot doesn't ship an AE policy out-of-the-box; we'd plug in our own encoder. |

## Data needs

- **Type**: observation-only — RGB images from the 3 wrist cameras (and optionally F/T + joints as auxiliary modalities).
- **Amount**: 10k–50k images for VAE; 100k+ for MAE. Easy to reach if we run CheatCode (or even WaveArm) headless for a few hours.
- **Distribution requirements**: every NIC index, every plug type, every board pose bucket, full grasp-noise range. Coverage matters more than count.
- **Collection strategy**: [`../10_data/07_self_supervised_obs.md`](../10_data/07_self_supervised_obs.md) (primary) + [`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md) byproduct (the demo pipeline emits observations anyway).
- **Overlap with other methods**: the same observation dataset trains [[repr-mae]] (file `19`). The demo dataset that **also** has actions trains [[il-bc]], [[il-act]], [[il-diffusion-policy]], etc. ★ This is why the keystone pipeline is so high-leverage.

## Compute & time

- **CNN VAE, 256×256, batch 64, 16 GB VRAM**: comfortably fits.
- **Training time** on RTX 2000 Ada with ~50k images: ~4–8 hours for a from-scratch β-VAE. Add 25% for auxiliary losses.
- **VQ-VAE** is somewhat trickier (codebook collapse) but similar wall-clock.
- **Inference**: ~5–10 ms / image at 256×256 on the desktop; well within the 50 ms / 20 Hz budget. Multi-camera: process all 3 in parallel or run a shared trunk + 3 heads.

## Best simulation environment

**Mostly indifferent**. Pretraining on Gazebo images is fine. Mixing Isaac Lab and MuJoCo renders **adds visual variety** that helps the latent generalize — especially useful for Phase 2 sim-to-real bets. For Qualification: Gazebo-only is sufficient if DR is aggressive.

## Auto-research applicability

**High fit.** Many tunable axes, fast per-iteration, easy to evaluate.

Tunable axes:
- Latent dim (32 / 64 / 128 / 256)
- β coefficient (0.5 / 1 / 2 / 4)
- Backbone (ResNet-18 vs ResNet-34 vs ViT-Tiny)
- Aux-loss weights (recon / port-loc / plug-cls)
- Augmentation strength (color jitter, crop, masking %)
- Training dataset size & balance

Iteration sketch:
```
1. Sample one config from the hypothesis distribution.
2. Train AE on a fixed observation dataset (~30 min on subset).
3. Freeze AE; train a small BC head on a fixed demo dataset (~10 min).
4. Eval head on 50 held-out trials in headless Gazebo (~30 min).
5. Log (config, head-eval score). Update hypothesis dist.
```

Per iteration: ~1.5 hours. 24 iterations / day on one desktop. **Karpathy fit: high** — clear axes, fast loop, measurable signal. See [`../10_data/12_auto_research_loop.md`](../10_data/12_auto_research_loop.md).

## My note: top-30 probability — **n/a standalone; moderate-to-high paired**

Pure AE = no actions = no score. The relevant question is: **does AE-as-front-end improve the downstream policy enough to matter?**

Honest read: **with the right auxiliary losses (port-location supervision, plug-type cls), an AE front-end can shave ~30% data and ~30% inference cost vs. learning the encoder end-to-end with the policy.** That's a real edge but not a category-changer.

- If the policy head is the bottleneck (small data, weak arch), AE pretrain helps a lot.
- If the policy head is strong (Diffusion Policy with a large ResNet trunk), AE adds little — the policy learns its own features just fine.

A strong path: **AE pretrain → Diffusion Policy head with the encoder frozen for the first N epochs, then unfrozen.** This is the most defensible version of the team-autoencoder identity.

## Priority for our project — **2 of 5**

Reasons it's important:
- Team identity revolves around it. Worth investing in to validate or disprove it.
- The data overlaps with IL pipelines we'd build anyway.
- Auto-research-friendly: gives our autonomous loop something tractable to optimize.

Reasons it's not #1:
- It's a means, not an end. We still need a policy head, and that's where most of the variance in score comes from.
- Pretrained vision encoders (file `18`) may beat us at our own game with no training. We should benchmark vs. R3M / VC-1 / DINOv2 frozen features before committing to a from-scratch AE.

## Recommended concrete plan

1. **Build the observation collection pipeline** (10_data/07).
2. **Train a baseline β-VAE** with port-location aux loss (target: visualize the latent and confirm it encodes port location).
3. **Compare** against frozen DINOv2 features on a downstream BC head. Pick the winner.
4. **Move the encoder choice into the auto-research loop** for hyperparameter search.

## Cross-refs

- Closely paired with [[repr-mae]] (file `19`) — same family, different masking strategy.
- Competes with [[repr-pretrained]] (file `18`) — frozen pretrained features are the strong baseline to beat.
- Feeds [[il-bc]], [[il-act]], [[il-diffusion-policy]], [[il-vqbet]], [[il-force-aware]], [[rl-residual]], [[rl-hil-serl]] as a front-end.
- Self-sup data → [[self-supervised-obs]] ([`../10_data/07_self_supervised_obs.md`](../10_data/07_self_supervised_obs.md)).
- Demo data → [[offline-scripted-groundtruth]] ([`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md)).
