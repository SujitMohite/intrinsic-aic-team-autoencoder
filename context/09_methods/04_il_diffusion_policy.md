# Diffusion Policy + 3D Diffuser Actor + DP3 + RDT-1B

## TL;DR

**Diffusion Policy** (Chi et al. 2023) frames visuomotor policy as conditional **denoising of action chunks**: given an observation, generate the next K actions by reverse-diffusing from Gaussian noise. The diffusion formulation natively handles **multimodal action distributions** — exactly the regime where vanilla BC (file `02`) collapses by averaging. Standard reference today for manipulation; in LeRobot as a first-class policy class. Extensions: **3D Diffuser Actor** (3D scene tokens, RLBench SOTA), **DP3** (3D-DP with tiny sparse-point-cloud encoder, 85% on 4 real tasks with 40 demos), **RDT-1B** (1B params, ALOHA-class). For AIC, vanilla 2D Diffusion Policy is the **strong baseline tied with [[il-force-aware]] for the primary path**.

## Why this could work for AIC

- **Multimodal action distributions handled natively.** Cable insertion has natural multimodality (which side to approach NIC from, search spirals around alignment). Diffusion captures this; BC averages it.
- **Action chunks** match short-horizon control needs. Standard chunk lengths 8-16; we'd use 16-32.
- **LeRobot first-class.** `lerobot/policies/diffusion/` ships ready-to-train; same data path as ACT.
- **Excellent on contact-rich** in published results — Chi et al. show +46.9% over baselines across 12 tasks.
- **DP3 variant is extremely sample-efficient** (40 demos, 85% real success) — *if* we add depth/point cloud.
- **F/T conditioning** is a clean state-vector extension; FoAR demonstrates the recipe.

## Why this could fail for AIC (skeptical)

- **Inference latency is the concern**. Standard DP with 10 denoising steps takes 50-100 ms on RTX-class. At 20 Hz observation cadence, this is borderline. **Mitigations**:
  - **RTC (Real-Time Chunking)** — LeRobot trick where the policy's next chunk is computed *while* the current chunk plays out. Hides latency entirely.
  - **DDIM / fewer steps** (10 → 4) at modest quality loss.
  - Smaller backbone (ResNet-18 → 18; ViT-Tiny instead of -Small).
- **DP3 needs depth.** Our 3 wrist RGB don't directly give depth. We could add a stereo depth estimator (off-the-shelf MiDaS or fake stereo from the side cameras) — extra engineering. **Without depth, vanilla 2D DP is the realistic pick.**
- **5 mm tolerance unproven.** Published DP numbers are on coarser tasks (1+ cm tolerances usually). Sub-mm story comes from residual-RL on top (ResiP, file `10`).
- **RDT-1B is 1B params + ALOHA-pretrained**: borderline on 16 GB for LoRA-fine-tune; ALOHA pretrain isn't a great prior for our UR5e setup. Probably skip.

## Generalization analysis

| Axis | Generalizes? | Notes |
|---|---|---|
| NIC index 0–4 | strong if data covers it | The diffusion latent absorbs multimodality across NIC indices well. |
| Board pose & yaw | strong | Same. |
| Plug type (SFP / SC) | moderate; needs explicit task conditioning | Add `task.plug_type` and `task.port_name` embeddings to the conditioning. |
| Grasp-pose noise | strong | Action distribution includes recoveries. |
| Lighting / texture | depends on DR + encoder | Use DINOv2-frozen ([[repr-pretrained]]) as the front-end for max robustness. |
| Sim-to-real | weak natively | Standard IL transfer issue. Mitigate via DR. |

## Architecture choices

### Vanilla 2D DP

```
[3 cams (224×224)] → ResNet-18 stem → spatial tokens (per camera, mean-pool or attention)
[F/T (6), joints (6), TCP_pose (6), task embed] → MLP → state token
                                       ↓
                                       Transformer encoder (conditioning)
                                       ↓
[Noise chunk: K × 6 (Cartesian deltas)] → Transformer decoder (denoising)
                                       ↓
                                       Predicted action chunk
```

Hyperparameters that matter:
- **Denoising steps at inference**: 10 default; lower to 4-5 with DDIM for speed.
- **Action chunk length K**: 16-32.
- **Action representation**: Cartesian deltas in `gripper/tcp` frame.

### F/T-conditioned DP (FoAR-style)

Add a small temporal F/T branch + future-contact-prediction auxiliary head. From the IL/VLA agent report: FoAR significantly outperforms RISE on 50 demos/task in contact-rich. **Likely our best practical version**.

### 3D variants — when applicable

- **DP3**: needs sparse point cloud. We don't have one natively; could compute from stereo. Decision: only invest if 2D plateaus.
- **3D Diffuser Actor**: needs 3D feature field. Heavier; ~24 GB borderline.
- **RVT-2**: virtual view rendering. Needs depth.
- **RISE**: 3D + DP head. Same caveat.

### Real-Time Chunking (RTC)

Inference-time inpainting trick: while chunk N is playing out, compute chunk N+1 with the first few actions copied from chunk N. Hides 50-100 ms of denoising latency. Supported in LeRobot. **Use this regardless of which variant.**

## Key resources

| Resource | Year | What |
|---|---|---|
| Chi et al., "Diffusion Policy" | 2023 | arXiv 2303.04137. The reference. |
| **`real-stanford/diffusion_policy`** | maintained | <https://github.com/real-stanford/diffusion_policy> |
| **LeRobot Diffusion Policy** | maintained | First-class `lerobot/policies/diffusion/` |
| Ke et al., "3D Diffuser Actor" | 2024 | arXiv 2402.10885. <https://github.com/nickgkan/3d_diffuser_actor> |
| Ze et al., "DP3" | 2024 | arXiv 2403.03954. <https://github.com/YanjieZe/3D-Diffusion-Policy> |
| Liu et al., "RDT-1B" | 2024 | arXiv 2410.07864. <https://github.com/thu-ml/RoboticsDiffusionTransformer> (active). |
| He et al., "FoAR" | 2024-25 | arXiv 2411.15753 — F/T-aware diffusion on RISE backbone. <https://github.com/Alan-Heoooh/FoAR> |
| Mini-Diffuser (RLBench-18 13h on one 4090) | 2025 | arXiv 2505.09430 |
| RTC (Real-Time Chunking) | 2025 | arXiv 2506.07339 |

## Data needs

- **Type**: (obs, action) demos. Action representation: Cartesian deltas. Include F/T in obs.
- **Amount**: DP typically thrives on **40-100 demos per task variant**. For our 5 NIC × 2 plug = 10 variants, target **500-2000 demos** for the full suite.
- **Distribution requirements**: cover all (NIC, plug, board pose, grasp noise) buckets evenly. DP's multimodality handling is wasted if data is unimodal.
- **Collection strategy**: [`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md). Same dataset as ACT and BC.
- **Overlap**: ★ shared dataset with BC, ACT, VQ-BeT, F/T-aware. Build once, train all.

## Compute & time

- **Vanilla DP (~80M params), 2k demos**: ~6-12 hours on RTX 2000 Ada. Comfortable in 16 GB at batch 32.
- **3D Diffuser Actor (~24 GB)**: borderline on 16 GB; use Mini-Diffuser variant (RLBench-18 in 13h on 4090) for our hardware.
- **DP3 (lightweight)**: ~6-8 hours on 16 GB.
- **RDT-1B (1B)**: LoRA only at our scale; 12-24 hours; **don't recommend** as primary.
- **Inference**:
  - Vanilla DP with 10 steps: ~80 ms per chunk on RTX 2000 Ada. Borderline.
  - With DDIM 4 steps: ~30 ms. Comfortable.
  - With RTC: hidden behind chunk execution. **Effectively zero perceived latency.**

## Best simulation environment

**Gazebo for training** (matches eval). For 3D variants we'd need depth — could rely on Gazebo's stereo cameras or simulate depth from the existing 3 wrist cams.

## Auto-research applicability

**High fit.**

Tunable axes:
- Denoising step count (4 / 10 / 20)
- Chunk size K
- Backbone (ResNet-18 / ResNet-34 / DINOv2-S / DINOv2-B)
- Action representation (Cartesian / joint deltas)
- F/T conditioning architecture (concat / cross-attend / FoAR-style)
- RTC delay (0 / 100 / 300 ms)
- DR strength (mild / aggressive)

Iteration: ~6-12 hr train + 30 min eval → ~10 hr/iter. ~2 iter/day. Karpathy fit: **high** — clear axes, fast measurable signal.

## My note: top-30 probability — **high**

- **Best case** (vanilla DP + F/T + good DR + RTC): 60-75 Tier 3 / trial × 3 = 180-225 + Tier 2 ~20 each → **240-285 total**. Top-30 strong.
- **Likely case** (vanilla DP + F/T concat): 55-65 Tier 3 / trial × 3 = 165-195 + Tier 2 ~15 each → **210-240**. Top-30 plausible.
- **Worst case** (vanilla DP, no F/T, no DR): 30-40 Tier 3 / trial × 3 = 90-120 → mid-pack.

**Path to top-30**:
1. Train F/T-conditioned 2D DP on the keystone dataset.
2. Use DINOv2-frozen ([[repr-pretrained]]) as the front-end (saves compute, better generalization).
3. Add aggressive image DR + F/T noise.
4. Use RTC at inference.
5. Optionally: residual RL ([[rl-residual]]) on top for the contact endgame.

**Risk factors**:
- Latency (mitigated by RTC).
- 3D variants tempting but engineering cost too high relative to gain on 2D + F/T.

## Priority for our project — **1 of 5** (tied with [[il-force-aware]])

Run alongside F/T-ACT as parallel primary bets. Same data pipeline; pick the winner.

## Cross-refs

- Sibling IL methods: [[il-bc]] (file `02`), [[il-act]] (file `03`), [[il-vqbet]] (file `05`).
- Add F/T → [[il-force-aware]] (file `06`); the natural marriage.
- 3D variants → [[il-3d]] (file `07`).
- VLA-scale diffusion: [[vla-smolvla-pi0]] (file `15`) — π0 is essentially diffusion-policy with a VLM backbone.
- Front-end encoder → [[repr-pretrained]] (file `18`) for DINOv2-frozen baseline; [[repr-autoencoder]] (file `17`) for our own.
- Residual RL refinement → [[rl-residual]] (file `10`).
- Data → [[offline-scripted-groundtruth]] ([`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md)).
