# Force-Aware Imitation Learning — ForceMimic, FoAR, ForceVLA, ManipForce, Bi-ACT

## TL;DR

**The most directly relevant cluster of methods in the entire IL literature for our problem.** 2024–2025 papers explicitly tackle F/T-conditioned imitation learning for contact-rich manipulation: ForceMimic, FoAR, ForceVLA, ManipForce/FMT, Bi-ACT, FILIC, STS-IL. Consistent finding across all of them: **adding F/T to a policy's input yields +12–33 percentage points** over RGB-only on contact tasks. For cable insertion at 5 mm tolerance with a wrist F/T sensor, this is the highest-EV thing we could do in our policy design.

## Why this could work for AIC

- **Cable insertion is fundamentally a contact-force problem.** The decisive moment is the 5 mm endgame, where vision saturates and F/T tells the story.
- **The data is essentially free.** Our keystone pipeline ([`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md)) already records `obs.wrist_wrench`. We just have to use it.
- **Published gains are large and consistent.** ForceVLA: +23.2% over π0 with 80% plug-insertion. FoAR: significant outperformance vs RISE on 50-demo tasks. Bi-ACT: shows F/T-aware ACT beats vanilla ACT on contact phases.
- **Method-agnostic.** "F/T-aware" is an architectural pattern, not a single method — applies on top of ACT, Diffusion Policy, π0, or SmolVLA.
- **LeRobot-friendly.** A vanilla ACT or DP in LeRobot already accepts a state vector — we just extend the state vector with F/T. Bi-ACT is essentially that.

## Why this could fail for AIC (skeptical)

- **None of these methods is "first-class" in LeRobot.** FoAR / ForceVLA / ManipForce have no LeRobot integration — we'd implement Bi-ACT-style F/T extension by hand on top of LeRobot ACT or DP. That's ~50-200 lines of code; small but a real cost.
- **F/T in sim is cleaner than in real.** The Gazebo F/T model is smooth; real F/T has bias drift, hysteresis, and impulsive noise. Skills trained on smooth F/T may overfit. Mitigation: add noise to F/T at training time (covered in [`../10_data/08_synthetic_dr.md`](../10_data/08_synthetic_dr.md)).
- **The most precise version — ForceVLA on top of π0 — is borderline on 16 GB.** π0 is 3.3B params; LoRA fits but only barely. ForceMimic and Bi-ACT-style ACT extensions are the practical picks.
- **F/T may dominate the policy.** Once the policy learns F/T's information value, it may stop attending to vision, then fail when F/T is uninformative (free space approach). Mitigation: train with random F/T dropout.
- **"Force-aware" published numbers are on different tasks** (FoAR: rope/cloth; ForceVLA: peg, plug; ManipForce: spread sauce). The +12-33pp number is a *cluster average*, not a guarantee for cable insertion at 5mm.

## Generalization analysis

| Axis | Generalizes? | Notes |
|---|---|---|
| NIC index 0–4 | strong if data covers it | Same as vanilla ACT/DP. |
| Board pose & yaw | strong | F/T input is roto-translation invariant in the gripper frame — extra robustness. |
| Plug type (SFP/SC) | moderate | F/T signatures differ between plug types; explicit conditioning still recommended. |
| Grasp-pose noise | **strong** | This is where F/T-aware shines: the policy can detect that contact is off-axis and correct in-loop. |
| Lighting / texture | moderate (visual augment dependent) | F/T modality is invariant to lighting; if vision branch is well-regularized, robust. |
| Sim-to-real | unproven for us | F/T model differences are a real issue. Train with F/T noise to hedge. |

## Method ingredients

### Variant A — Bi-ACT-style F/T concat

Smallest change. Take the LeRobot ACT policy, extend the state vector to include `[joints (6), TCP_pose (6), wrist_wrench (6), task one-hot]` instead of just `[joints, TCP_pose]`. Train identically. **Our likely first attempt.**

### Variant B — Dedicated F/T branch + cross-attention

Build a small F/T encoder (MLP or temporal Conv on a short F/T history) that emits its own tokens, fed to the policy transformer alongside visual tokens via cross-attention. FoAR-style.

### Variant C — F/T-MoE on top of a VLA (ForceVLA)

Mixture-of-experts over visual / F/T / language. For π0-class backbones. High-ceiling but ≥24 GB friendly to train cleanly.

### Variant D — Tactile-conditioned diffusion (Reactive Diffusion Policy)

Diffusion policy that re-denoises actions in response to recent tactile / F/T signals. Best for the contact phase. Latency higher than chunked policies.

For AIC, **Variant A first** (cheapest, ~80% of the gain expected). Move to B if A plateaus.

## Key resources

| Resource | Year | What |
|---|---|---|
| Liu et al., "ForceMimic" | 2024 | Handheld ratchet rig + hybrid force-position IL. arXiv 2410.07554 |
| He et al., "FoAR" (RA-L 2025) | 2024 | RISE + future-contact predictor + F/T gating. arXiv 2411.15753. <https://github.com/Alan-Heoooh/FoAR> |
| Yu et al., "ForceVLA" | 2025 | π0 + force MoE → 80% plug insertion. arXiv 2505.22159 |
| Kobayashi et al., "Bi-ACT" | 2024 | Bilateral teleop F/T + ACT. arXiv 2401.17698. <https://github.com/ogata-lab/bi-act> |
| "ALPHA-α / Bi-ACT" | 2024 | Force-aware extension. arXiv 2411.09942 |
| "Bi-LAT" | 2025 | Language + force ACT. arXiv 2504.01301 |
| ManipForce / FMT | 2025 | Frequency-aware multimodal transformer. arXiv 2509.19047 |
| Reactive Diffusion Policy (CoRL 2025) | 2025 | Tactile-conditioned diffusion. <https://reactive-diffusion-policy.github.io/> |
| LeRobot ACT base | maintained | Drop-in: extend state vector dimension. <https://github.com/huggingface/lerobot> |
| **`aic_example_policies/aic_example_policies/ros/RunACT.py`** | this repo | Our starting integration point — extend it. |

## Data needs

- **Type**: (obs, action) demos with **F/T included in obs**. Our keystone pipeline records this by default.
- **Amount**: 500-2000 demos (same as ACT). F/T information is dense, so smaller datasets can work.
- **Distribution requirements**:
  - Cover the full F/T regime: free-space, light contact, sustained insertion force, off-axis contact.
  - **Inject controlled grasp-noise variation** so the policy sees a range of F/T → action mappings.
  - **Add successful AND near-successful (but not jammed) trajectories** so the policy can learn recovery.
- **Collection strategy**: [`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md). Critically, instrument CheatCode to actually use F/T feedback (modify it to back-off on excessive force) so demos contain force-reactive behavior — otherwise the learned policy never has to react to F/T.
- **Overlap**: same dataset as [[il-bc]], [[il-act]], [[il-diffusion-policy]]. The F/T is already in there.

## Compute & time

- **Variant A** (Bi-ACT-style F/T concat into LeRobot ACT): same compute as ACT (file `03`) — ~6 hours training.
- **Variant B** (F/T cross-attention branch): +20% params, +15% compute. ~7 hours.
- **Variant C** (ForceVLA on π0): LoRA + frozen VLM expert + train action expert — 12-24 hours, tight on 16 GB.
- **Inference latency**: identical to base method (F/T branch is tiny).

## Best simulation environment

**Gazebo for training and eval.** F/T from Gazebo matches eval F/T exactly. If we mix Isaac / MuJoCo training data, F/T values may differ enough to confuse the policy — pin to Gazebo F/T unless explicitly randomizing.

## Auto-research applicability

**High fit.**

Tunable axes:
- F/T history length (1, 4, 16 timesteps)
- F/T encoding (concat vs MLP vs temporal Conv)
- F/T dropout probability (0%, 25%, 50%) — robustness regularizer
- F/T noise during training (σ_force, σ_torque)
- Loss weighting between vision-dominant and F/T-dominant timesteps
- Base policy (ACT / DP / VQ-BeT)

Each iter: ~6-8 hour train + 30 min eval. ~3 iter/day on the desktop. Karpathy fit: **high**. The F/T-aware design is exactly the kind of "small editable surface" autoresearch handles well — vary one hyperparameter, eval, repeat.

## My note: top-30 probability — **high**

Of all the IL methods in our list, this one has:
- The biggest published gains over generic IL on contact-rich tasks (+12-33pp).
- The smallest implementation burden on top of our existing toolkit (LeRobot ACT + extended state).
- A direct narrative fit ("the cable insertion problem cares about force, so the policy should see force").

**Estimated path to top-30**:
- Build the keystone CheatCode pipeline ([`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md)) with **F/T-reactive CheatCode** (modify CheatCode to back off on contact force).
- Train Bi-ACT-style F/T-ACT on the resulting demos.
- Add image DR ([`../10_data/08_synthetic_dr.md`](../10_data/08_synthetic_dr.md)) and F/T noise.
- Expected Tier 3: 60-75 per trial × 3 = 180-225, plus Tier 2 of ~20 per trial → **220-280 total** → top-30 likely.

**Risk factors**:
- If our scripted demos don't actually use F/T (CheatCode in upstream is feedforward, not F/T-reactive), the F/T-aware policy has nothing to learn from F/T. Modifying CheatCode is mandatory.
- Sim-to-real Phase 2 may break if F/T noise model differs.

## Priority for our project — **1 of 5** (tied)

Run alongside [[il-diffusion-policy]] (file `04`) as the two parallel primary bets. They share the same data; we pick the winner empirically.

## Cross-refs

- Direct extension of [[il-act]] (file `03`) and [[il-diffusion-policy]] (file `04`).
- Pairs naturally with [[hybrid-classical-learned]] (file `21`) — force-aware learned residual on top of classical approach.
- Closest RL analog: [[rl-hil-serl]] (file `12`) — same F/T-fusion philosophy with online RL refinement.
- Data → [[offline-scripted-groundtruth]] ([`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md)) — but **modify CheatCode to be F/T-reactive first**.
- DR layer → [[synthetic-dr]] ([`../10_data/08_synthetic_dr.md`](../10_data/08_synthetic_dr.md)).
- Auto-research applicable: [[auto-research-loop]] ([`../10_data/12_auto_research_loop.md`](../10_data/12_auto_research_loop.md)).
