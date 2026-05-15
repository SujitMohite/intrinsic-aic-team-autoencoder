# Behavior Cloning (vanilla)

## TL;DR

Treat (observation, action) pairs from demonstrations as supervised learning. Train a network — MLP, CNN+MLP, or Transformer — to predict the demonstrator's next action given the current observation. **Simplest possible imitation method.** The "tabula rasa" baseline that every other IL method is measured against. For AIC, vanilla BC is the floor; everything fancier needs to beat it.

## Why this could work for AIC

- **Trivial to implement.** A few hundred lines of PyTorch + LeRobot's existing dataloader.
- **Fast to train.** A small CNN+MLP on 5k demos trains in 1–3 hours on the desktop.
- **Cheap inference.** ~5 ms / step at 50M params. Easily fits the 20 Hz observation rate.
- **Maximally leverages CheatCode-auto-data.** No special data needed beyond `(obs, action)`. Maps 1:1 onto [`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md).
- **Excellent A/B baseline.** Differences between BC and a fancier method tell us whether the fancier method is worth its complexity.

## Why this could fail for AIC (skeptical)

- **Compounding error / distribution shift.** BC is fragile to states the demonstrator never visited. As soon as our learned policy makes a small mistake, it drifts off the demo manifold and goes off-script. This is **the** classical IL pathology (Ross et al. DAgger 2011 onwards).
- **Mode collapse on multimodal demos.** CheatCode usually picks the same approach trajectory each time; vanilla BC averages multimodal demos and produces a wishy-washy mean action. Cable insertion has natural multimodality (left vs right pre-insertion approach, multiple grasps of an SC port).
- **Doesn't naturally use F/T sensor.** A vanilla BC will concat F/T into the input but won't learn to *react* to force events (the supervisor — CheatCode — doesn't really react to force either; it knows the target pose). The policy stays open-loop on contact.
- **Likely plateau at 30–50 Tier-3 points/trial.** Enough for some Tier-3 proximity reward but not for the 50–75 zone we want.

## Generalization analysis

| Axis | Generalizes? | Notes |
|---|---|---|
| NIC index 0–4 | depends on data | Trained on all 5 → likely yes. Trained on subset → no. |
| Board pose & yaw | weak-moderate | Vision input handles this in principle; in practice BC overfits to demo distribution. |
| Plug type (SFP / SC) | weak | Mode collapse between the two unless we condition explicitly on `task.plug_type`. |
| Grasp-pose noise | weak | Demos with random grasp give the policy variance but BC averages it out. |
| Lighting / texture | weak | DR mandatory. |
| Sim-to-real | very weak | Classic IL transfer pathology. Don't expect Phase 2 transfer. |

## Architecture choices

### A. Simple visuo-motor: 3-cam CNN + state MLP + action MLP head

```
[3 cams]  → ResNet-18 (shared) → 3 × 512 → concat → 1536
[F/T (6)] → small MLP        → 64
[joints]  → small MLP        → 64
[task one-hot] → 16
                                       concat
                                       ↓
                                       MLP (2-4 layers) → 6-D Cartesian delta + 6-D stiffness
```
~25M params. Trains in ~3 hours on RTX 2000 Ada with 5k demos.

### B. Transformer-policy (BeT-like minus VQ)

Treat (obs, action) as token sequence; transformer predicts next action token. Better at handling history. Similar params and training time. The architectural backbone for ACT.

### C. Action-chunking BC

Predict the next K actions at once (chunk = 4-16). Reduces compounding error vs single-step BC. This is essentially what ACT does — see file `03`. Strictly more expressive than vanilla BC.

For AIC, **start with A**; if it plateaus, move to ACT (which is action-chunked BC with a transformer + VAE head).

## Key resources

| Resource | Year | What |
|---|---|---|
| Pomerleau, "ALVINN" / "Efficient Training of Artificial Neural Networks for Autonomous Navigation" | 1989 | The original BC paper (driving). |
| Ross, Gordon, Bagnell, "DAgger" | 2011 | The covariate-shift fix; iteratively query the expert. Relevant if we add HIL later. |
| Florence et al., "Implicit Behavior Cloning" | 2021 | Implicit BC (energy-based). Better at multimodal demos. arxiv 2109.00137 |
| Brohan et al., "RT-1" | 2022 | Large-scale BC with transformer; the precursor to RT-2 and OpenVLA. arxiv 2212.06817 |
| **HuggingFace LeRobot** | maintained | <https://github.com/huggingface/lerobot> — ships BC trainers + ACT + DP. Use the BC trainer for the vanilla baseline. |
| **`lerobot/policies/bc.py`** | maintained | Reference impl. |
| `imitation` (HumanCompatibleAI) | maintained | A broader IL library with DAgger / GAIL / AIRL. <https://github.com/HumanCompatibleAI/imitation> |

## Data needs

- **Type**: (obs, action) demos.
- **Amount**: minimum ~500 successful episodes to get *something*; 2000–5000 for a credible baseline.
- **Distribution**: cover all axes; bias toward edge cases (extreme NIC yaw, far board poses).
- **Collection strategy**: [`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md). The keystone pipeline gives us this directly.
- **Overlap with other methods**: ★ same dataset feeds ACT, Diffusion Policy, VQ-BeT, F/T-aware IL. **The decision to build the keystone pipeline pays off here first.**

## Compute & time

- **Training**: ~25M model, batch 64, 5k demos × 150 steps ≈ 750k samples × 100 epochs → 3-hour training on RTX 2000 Ada. Easily fits 16 GB.
- **Inference**: ~5 ms / step. Plenty of headroom under the 50 ms / 20 Hz budget.
- **Total wall-clock (data + train + eval)**: 2–3 days assuming the keystone pipeline is ready and producing demos.

## Best simulation environment

**Gazebo** for demo collection (matches eval). MuJoCo or Isaac for additional out-of-distribution test data, optional.

## Auto-research applicability

**High fit.** Many cheap-to-vary axes:

- Architecture (ResNet-18 vs ResNet-34 vs ViT-Tiny)
- History length (1, 3, 8 steps)
- Action chunk size (1, 4, 8, 16)
- Loss (L1 vs L2 vs Gaussian NLL)
- Task conditioning (one-hot vs embedding vs text)
- Demo subset (full vs only successful vs only diverse)

Iteration: train (2 hr) + eval 50 trials (30 min) → 2.5 hr / iter on a single GPU. ~10 iter/day. Karpathy fit: **high**.

## My note: top-30 probability — **low to moderate**

- Reported BC numbers on insertion are mostly 20–50% success in the literature on similar peg/cable tasks. Translated to AIC scoring: ~30 Tier-3 per trial × 3 = 90, plus some Tier 2 → ~120 total. **Likely mid-pack, not top-30.**
- Best case (perfect data + task conditioning + sufficient diversity): ~50–60 Tier-3/trial = ~200 total. Could squeak into top-30 if competition is weak.
- Floor: 5–10 Tier-3 from compounding error. Still beats Tier-1-fail.

## Priority for our project — **4 of 5**

- **Worth building as the first IL baseline.** Tells us if the data is good enough at all.
- Don't expect this alone to win. But the same data feeds ACT (file `03`) and Diffusion Policy (file `04`) which have higher ceilings.
- If our auto-research loop is operational, vanilla BC is the **canary** — if BC scores plateau low, the data is the bottleneck, not the model.

## Cross-refs

- Strict superset: [[il-act]] (file `03`) is action-chunked BC with a VAE.
- Strict alternative: [[il-diffusion-policy]] (file `04`) handles multimodality natively.
- Force-aware variant: [[il-force-aware]] (file `06`).
- Data → [[offline-scripted-groundtruth]] ([`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md)).
- Auto-research loop applicable: [[auto-research-loop]] ([`../10_data/12_auto_research_loop.md`](../10_data/12_auto_research_loop.md)).
