# Team Approach — Autoencoder

STATUS: draft. **Not yet validated.** Update this file as decisions firm up.

> The team name (`team-autoencoder`) signals the intended approach. This document captures the current thinking. Replace `TODO` markers as we converge.

---

## See also (method landscape research, May 2026)

The full method comparison lives in [`../09_methods/00_index.md`](../09_methods/00_index.md). Data strategies in [`../10_data/00_index.md`](../10_data/00_index.md). The Karpathy-style autonomous research loop design is in [`../10_data/12_auto_research_loop.md`](../10_data/12_auto_research_loop.md). The variants below were sketched **before** the broader landscape was researched; some have since been refined. In particular:

- **AE alone is a force-multiplier, not a policy.** See [`../09_methods/17_repr_autoencoder.md`](../09_methods/17_repr_autoencoder.md).
- **Pretrained encoders (DINOv2 / Theia) may beat a from-scratch AE** on downstream control. See [`../09_methods/18_repr_pretrained.md`](../09_methods/18_repr_pretrained.md).
- **The current top-3 picks** (Diffusion Policy + F/T-ACT, Hybrid classical+learned, HIL-SERL) all sit *above* a representation-learning front-end. The autoencoder direction maps cleanest onto Variant 2 below paired with [Diffusion Policy](../09_methods/04_il_diffusion_policy.md) as the head.

## Hypothesis

A **learned visual representation** is the right level to attack cable insertion in AIC:

- Ground truth `/tf` is off-limits at eval, so we need a perception path.
- The Intrinsic Vision Model (IVM) is only available in Phase 1+, not Qualification.
- Pure end-to-end policies (ACT, diffusion) are demonstrated by the `RunACT` baseline but require lots of demos and don't expose a clean latent that we could analyse / debug.

A **compact autoencoder** trained on wrist-camera images (optionally conditioned on the task) gives us:

1. A small latent (e.g. 32–128 dim) summarizing the scene + target.
2. Visual robustness via reconstruction loss.
3. A fast policy head that conditions on `(latent, F/T, joint_state, controller_state)` → action.

---

## Candidate designs

### Variant 1 — Plain image VAE → small MLP policy

```
RGB (3 cams, 128x128) ──► VAE encoder ──► z (64-dim)
                                          │
F/T (6) ──────────────────────────────────┤
joints (6) ───────────────────────────────┤
controller_state (12) ────────────────────┤
                                          │
Task one-hot ─────────────────────────────┤
                                          ▼
                                       MLP policy ──► Cartesian delta (6)
```

Pros: simple, fast. Cons: VAE latent may not capture port location.

### Variant 2 — Goal-conditioned reconstruction

VAE is trained to **reconstruct** a target-port crop alongside the full image. Forces the latent to encode port location.

```
RGB ──► encoder ──► z
Task port_id ──► embedding ──► concat with z
z+e ──► decoder ──► (reconstructed image, predicted port pixel coords)
```

Pros: explicit visual grounding. Cons: needs labeled port locations during training (ground truth available).

### Variant 3 — AE + ACT

Train an image AE as a frozen front-end; train an ACT-style transformer policy on the latent + low-dim state.

Pros: leverages LeRobot infra. Cons: heavier than Variant 1.

**Tentative pick: Variant 2.** Goal-conditioned grounding addresses our key gap (no ground-truth port pose at eval) and the AE training data is cheap to produce.

---

## Training data plan

1. Spawn task board across the full randomization range using the training utils (`/expand_xacro`).
2. For each spawn:
   - Record the 3 wrist cameras at home pose + a few approach poses.
   - Log ground-truth port pose in the image (via `/scoring/tf` — training only).
3. ~5000 (scene, target) pairs across all NIC indices 0–4 and SC ports 0–1.
4. Optionally augment with Isaac or MuJoCo renders for robustness.

---

## Policy head plan

- Start with imitation from **CheatCode** rollouts. Cheap to generate: CheatCode in training mode gives many successful trajectories.
- Loss: BC on (latent + state → Cartesian delta).
- Inference: 10 Hz `MotionUpdate` with mild compliance (stiffness 60/60/60/40/40/40, wrench feedback gains for insertion).

---

## Milestones

| Date | Milestone | Status |
| --- | --- | --- |
| 2026-05-14 (today) | Repo familiarization + context docs (this) | done |
| 2026-05-14 | Run CheatCode locally, get `scoring.yaml` | TODO |
| 2026-05-14 | Scaffold `team_autoencoder/` package, smoke-test WaveArm clone in our package | TODO |
| 2026-05-15 | Submit a CheatCode-derived **non-cheating** policy as a fallback | TODO |
| Post-Qual | Pre-train AE, train BC head, submit AE policy (for Phase 1 dry runs) | TODO |

---

## Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| AE latent fails to capture port location | Variant 2 (goal-conditioned reconstruction) |
| Trained in Gazebo, fails on cloud Gazebo (RTF drift) | Use sim time everywhere; pad time budgets |
| Heavy model → blows discovery budget | Lazy load inside `insert_cable`; consider TorchScript export |
| Vision underperforms on plain Gazebo lighting | Image augmentation; sample from Isaac/MuJoCo renderings during AE pretraining |
| Sub deadline (May 15) too close to ship our AE | Submit CheatCode-derived rule-based fallback first, AE second |

---

## Open questions

- Cartesian deltas or joint deltas as the action head?
- Single policy for SFP and SC, or two heads with task-type routing?
- Include controller_state (current TCP) as input, or rely on the AE latent to ground position?
- Do we add wrist-camera depth via stereo from the two side cameras?
