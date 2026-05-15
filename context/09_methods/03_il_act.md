# ACT — Action Chunking with Transformers

## TL;DR

**ACT** (Zhao et al. 2023, "Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware") is a transformer encoder-decoder trained as a conditional VAE that **predicts a chunk of K future actions** (typically K=10-50) given a history of observations. The chunking dramatically reduces compounding error vs. single-step BC, and the VAE structure handles small multimodality in demonstrations. ACT is the **default LeRobot IL baseline** and the closest direct fit for AIC out of any IL method — the `RunACT.py` baseline already uses it.

## Why this could work for AIC

- **Already wired into our toolkit.** `aic_example_policies/aic_example_policies/ros/RunACT.py` shows the integration with LeRobot. We could literally start from a fork of this file.
- **Action chunking handles short-horizon control** very well — exactly what cable insertion needs (10-50 step trajectories).
- **VAE latent z dampens compounding error.** At inference, ACT samples z and predicts chunks open-loop for K steps before re-encoding; small temporal-ensembling tricks make this very stable in practice.
- **Multimodal-lite.** The Gaussian VAE z handles the *minor* multimodality of insertion paths (small grasp differences, NIC yaw variation).
- **Reasonable VRAM footprint.** ~100M params; fine-tunes comfortably on 16 GB.
- **Published wins on insertion-style tasks.** ACT's original paper does *bi-manual* fine manipulation (a similar contact-rich regime).

## Why this could fail for AIC (skeptical)

- **The VAE z still doesn't cover *severe* multimodality** like SFP vs SC plug types. Best to condition explicitly on `task.plug_type` and `task.port_name` rather than rely on z.
- **F/T integration is not native to the original ACT.** We must bolt-on a small F/T encoder branch (trivial, but slightly off the shelf).
- **Reported success on 5 mm insertion** — I'm not aware of a published number specifically on cable/port insertion under randomized board pose at exactly 5 mm tolerance. The bi-manual paper hits sub-mm via different means (high-frequency control + dual arms). Take that as encouragement, not as evidence we will hit it.
- **Demands consistent demo styles.** If our auto-collected CheatCode demos have weird artifacts (force spikes, IK jumps), ACT will learn them.
- **Open-loop chunks miss late-arriving F/T signals.** Between re-encodes, the policy can't react to a sudden contact. Mitigation: shorter chunks (K=10) for the contact phase; longer chunks for the approach.

## Generalization analysis

| Axis | Generalizes? | Notes |
|---|---|---|
| NIC index 0–4 | strong if data covers it | The transformer's attention scales naturally across positional variation. |
| Board pose & yaw | strong | Same. |
| Plug type (SFP / SC) | moderate; needs explicit conditioning | Use task one-hot or text embedding; don't rely on VAE z. |
| Grasp-pose noise | moderate | VAE z + augmentation help. |
| Lighting / texture | depends on DR | Pure ACT has no special invariance; DR is mandatory. |
| Sim-to-real | weak | Standard IL transfer problem. |

## Architecture choices

The canonical ACT architecture:

```
Observation history (last T steps; T=1-4 is fine):
  [3 cams (256×256)] → ResNet-18 stem → spatial tokens
  [F/T, joints, TCP pose] → linear → state tokens
  [task one-hot / port-name embed] → task token
                                       ↓
                                       Transformer encoder
                                       ↓
                                       VAE prior+posterior over z (32-D)
                                       ↓
                                       Transformer decoder → K future actions
```

Hyperparameters to consider:
- **Chunk size K**: K=16-32 is typical. For AIC, K=10 for contact phase, K=32 for approach.
- **Temporal-ensemble at inference**: average the next-N-step predictions across the last several encoder calls. Standard ACT trick; major improvement at zero training cost.
- **z dimension**: 32 default; smaller (8) for tighter mode coverage.

## Key resources

| Resource | Year | What |
|---|---|---|
| Zhao et al., "Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware" | 2023 | The ACT paper. arxiv: 2304.13705 |
| **LeRobot ACT impl**: `lerobot/policies/act/` | maintained | Reference code we'd use directly. <https://github.com/huggingface/lerobot> |
| **`aic_example_policies/aic_example_policies/ros/RunACT.py`** | this repo | Our integration point — already wires LeRobot ACT into the `aic_model` framework. |
| ALOHA Unleashed (Zhao et al. 2024) | 2024 | Extends ACT with diffusion head; modest gains. arxiv: 2410.13126 |
| BiACT (various 2024 forks) | 2024 | Bimanual variants; less relevant for our single-arm task. |
| Mobile ALOHA (2024) | 2024 | Adds mobile base; not relevant for AIC. |

## Data needs

- **Type**: (obs, action) demos, identical to BC.
- **Amount**: ACT works with **50–200 demos** on canonical tasks; for AIC with 5 NIC indices × 2 plug types, **bump to 500-2000** so each (NIC, plug) bucket has enough.
- **Distribution requirements**: same as BC; coverage matters more than count past ~500.
- **Collection strategy**: [`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md). Same exact dataset as BC.
- **Overlap**: identical to BC. Same demos feed [[il-bc]], [[il-diffusion-policy]], [[il-vqbet]], [[il-force-aware]].

## Compute & time

- **ACT (100M params)** + 5k demos: ~6 hours training on RTX 2000 Ada. Comfortable in 16 GB with batch 32-64.
- **Inference**: ~10-20 ms per encoder call. With chunk K=16 → encoder called every 16 steps, easily real-time at 20 Hz.
- **Total wall-clock (assuming demos ready)**: 1 day training + 0.5 day eval.

## Best simulation environment

**Gazebo for training** (matches eval). The encoder generalizes better if pretrained on a vision dataset (DINOv2 weights as ResNet-18 starting point is a cheap win). Cross-sim DR optional for Phase 2.

## Auto-research applicability

**High fit.**

Tunable axes:
- Chunk size K
- Encoder backbone (ResNet-18 / ResNet-34 / ViT-Tiny / DINOv2-frozen)
- VAE z dimension
- Temporal ensembling on/off
- Task conditioning representation
- F/T branch architecture (concat vs cross-attend)
- Loss weighting (L1 action loss + KL on z)
- Demo subset (which (NIC, plug) buckets)

Iteration: train (6 hr) + eval 50 trials (30 min) → ~7 hr / iter. ~3 iter / day. Karpathy fit: **high** for hyperparameter exploration but each iter is non-trivial wall-clock.

## My note: top-30 probability — **moderate-high**

- ACT is the proven baseline. Reported numbers on similar tasks (peg-in-hole, ALOHA-style) hit 60-90% success in published work.
- For AIC: with good data and F/T conditioning, I'd guess **50-65 Tier-3 / trial × 3 = 150-200 total**, plus Tier 2 of 15-20 per trial → **~200-260 total**. That's plausibly top-30 territory.
- Path to actually reach top-30:
  1. Build the [`02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md) pipeline with high distributional coverage.
  2. Add F/T as an input modality (see file `06`).
  3. Use task-port-name conditioning, not VAE z alone, for SFP vs SC.
  4. Aggressive image DR ([`../10_data/08_synthetic_dr.md`](../10_data/08_synthetic_dr.md)).
  5. Temporal ensembling at inference.

## Priority for our project — **2 of 5**

The strongest "boring" pick. ACT is well-understood, in LeRobot, has a working starter file in our repo, and the data overlaps with everything else. Don't underestimate it — strong baselines often win.

## Cross-refs

- Direct upgrade of [[il-bc]] (file `02`) — same data, better arch.
- Direct comparison to [[il-diffusion-policy]] (file `04`) — different multimodality handling.
- Direct extension: [[il-force-aware]] (file `06`) — F/T conditioned ACT.
- ACT + AE encoder front-end: [[repr-autoencoder]] (file `17`).
- Data → [[offline-scripted-groundtruth]] ([`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md)).
