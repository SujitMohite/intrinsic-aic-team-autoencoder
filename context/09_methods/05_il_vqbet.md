# VQ-BeT — Vector-Quantized Behavior Transformer

## TL;DR

**VQ-BeT** (Lee et al. 2024) is a transformer policy that **discretizes the action space via hierarchical residual vector quantization** and predicts action tokens (plus a small continuous residual). The discretization gives multimodal coverage similar to Diffusion Policy but with **10-20× faster inference** (no denoising at inference). LeRobot-first-class. Best fit when you want multimodality at low latency, and an alternative bet to Diffusion Policy.

## Why this could work for AIC

- **Inference < 10 ms.** With 20 Hz control budget (50 ms), VQ-BeT leaves time for everything else.
- **Multimodal action distributions handled** — like Diffusion Policy, beats vanilla BC's averaging.
- **LeRobot first-class** (`vqbet` policy class). Same data path as ACT / DP.
- **Small VRAM footprint.** ~80M params; trains comfortably on 16 GB at batch 64.
- **F/T input is a state-vector concat** — trivial extension.

## Why this could fail for AIC (skeptical)

- **No published cable / peg insertion at sub-cm tolerance.** VQ-BeT reports parity with Diffusion Policy on Franka-Kitchen and PushT — both coarse tasks. **5 mm tolerance is speculative.**
- **Codebook collapse** is a real failure mode. Symptoms: most actions snap to a few codes; policy diversity drops. Mitigation: large codebook (256+), residual head to recover precision, careful learning-rate tuning.
- **Discrete action space can hurt precision.** The continuous residual head only goes so far. For sub-cm insertion, residual quantization might lose information.
- **Less proven than ACT or Diffusion** for contact-rich. Sits in the "fast and elegant" niche.

## Generalization analysis

| Axis | Generalizes? | Notes |
|---|---|---|
| NIC index 0–4 | strong if data covers it | Same as ACT/DP. |
| Board pose & yaw | strong | Same. |
| Plug type (SFP/SC) | weak natively; explicit conditioning needed | Different plug types occupy different code-clusters. Force a task-id input. |
| Grasp-pose noise | moderate | Discretization may smooth over fine residual. |
| Lighting / texture | depends on encoder + DR | Standard. |
| Sim-to-real (Phase 2) | weak natively | IL transfer issue. |

## Architectural sketch

```
[Obs: imgs + F/T + joints + TCP + task one-hot] → encoder → state token
                                       ↓
                                       Transformer
                                       ↓
                            Action token (discrete VQ-VAE)
                                       +
                            Continuous residual (small MLP)
                                       =
                            Final action
```

The hierarchical residual VQ allows multiple levels of granularity. Default: 2 levels × 256 codes each = 256² effective bins; small continuous residual on top.

## Key resources

| Resource | Year | What |
|---|---|---|
| Lee et al., "Behavior Generation with Latent Actions" (VQ-BeT) | 2024 | ICML 2024. arXiv 2403.03181 |
| Shafiullah et al., "Behavior Transformers" (BeT) — the precursor | 2022 | arXiv 2206.11251 |
| **LeRobot VQ-BeT** | maintained | First-class `lerobot/policies/vqbet/` |
| **`jayLEE0301/vq_bet_official`** | maintained | Reference impl. |
| VQ-VLA (extension) | 2025 | VQ tokenization for VLAs. Recent. |

## Data needs

- **Type**: (obs, action) demos. Same as ACT, DP.
- **Amount**: 50-200 per task variant works; 500-2000 total for our full suite.
- **Distribution**: cover all NIC × plug × pose buckets. Critical for codebook coverage.
- **Collection strategy**: [`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md).
- **Overlap**: ★ shared dataset with all IL methods.

## Compute & time

- **Training**: ~4-6 hours on 16 GB at batch 64, 2000 demos.
- **Inference**: < 10 ms / chunk. The fastest learned policy in our list.
- **VRAM**: 16 GB comfortable.

## Best simulation environment

**Gazebo** for training and eval. F/T model consistency matters.

## Auto-research applicability

**High fit.**

Tunable axes:
- Codebook size per level (64 / 256 / 1024)
- Number of VQ levels (1 / 2 / 3)
- Residual head depth
- Chunk size
- Encoder (DINOv2-frozen vs ResNet-18 trained)
- F/T input dimension

Iteration: ~5 hour iter. ~3-5 iter/day. Karpathy fit: **high** — fast training, clear measurable axes.

## My note: top-30 probability — **moderate**

**Best case**: 50-60 Tier 3 / trial × 3 = 150-180 + Tier 2 ~18 → **205-235**. Top-30 plausible.

**Likely case**: 35-50 Tier 3 → mid-pack.

**Risk factors**:
- Codebook collapse (have to monitor + tune).
- No published sub-cm insertion validation.

**Path to top-30**:
1. Implement on the keystone dataset.
2. Treat as one of the parallel IL bets (alongside ACT, DP, F/T-aware).
3. Compare downstream eval against ACT + DP under identical conditions.

## Priority for our project — **3 of 5**

- Worth implementing as one of the parallel IL bets — same data, different policy class.
- **Cheap to run** — 5-hour training. We can include it in the autoresearch sweep.
- Don't expect it to dominate; expect it to either tie ACT/DP or surface a niche where its multimodality + low latency wins.

## Cross-refs

- Direct alternatives: [[il-act]] (file `03`), [[il-diffusion-policy]] (file `04`).
- Force-aware extension: same pattern as [[il-force-aware]] (file `06`) — VQ-BeT with F/T concat.
- Encoder front-end: [[repr-pretrained]] (file `18`) for DINOv2-frozen; [[repr-autoencoder]] (file `17`) for our own.
- Data → [[offline-scripted-groundtruth]] ([`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md)).
- Auto-research applicable: [[auto-research-loop]] ([`../10_data/12_auto_research_loop.md`](../10_data/12_auto_research_loop.md)).
