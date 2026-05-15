# GR00T N1 / N1.5 / N1.7, Helix, Gemini Robotics — Newer VLAs

## TL;DR

**NVIDIA GR00T N1** (Mar 2025, 2B params, humanoid-targeted, System1/System2 architecture) and **GR00T N1.5 / N1.7** (May 2025, 3B, supports SO-100/101 LeRobot arms). **Helix** (Figure, Feb 2025) is closed-source on-board humanoid VLA — not usable. **Gemini Robotics 1.5 / ER 1.5** (DeepMind, Sep 2025) — ER 1.5 is API-only embodied-reasoning VLM; full VLA is partner-only — not usable. For AIC: only **GR00T N1.5+ with the `--no-tune_diffusion_model` flag** is operationally available on 16 GB; UR5e + Hand-E is *off* its pretraining distribution. **Marginal expected value for our task; do not prioritize.**

## Why this could (in principle) work for AIC

- **NVIDIA-backed.** sm_89-friendly. Isaac sim integration. Growing LeRobot bridge.
- **System1 (reflex) + System2 (VLM reasoning)** dual architecture — interesting design.
- **A community paper (2512.01358) shows adding F/T to GR00T proprioception boosts performance to 94% on a contact-rich task.** Suggests F/T fusion works on this backbone.
- **First-class LeRobot SO-101 path** is the closest analog to UR5e — could probably be adapted.

## Why this would actually fail (skeptical)

- **Humanoid-centric pretraining (GR1, G1).** UR5e + Hand-E is off-distribution. The cross-embodiment prior may not transfer cleanly to our arm.
- **16 GB requires `--no-tune_diffusion_model` flag**, which hurts quality. Default FT wants ~25 GB.
- **Non-trivial UR5e integration.** Engineering cost: 1-2 person-weeks to wire up the embodiment tag + LeRobot adapter.
- **Closed-data.** We can't inspect what GR00T was trained on; our task may or may not be in distribution.
- **No published sub-cm cable insertion**. Like every VLA in this neighborhood.

## Helix (Figure)

**Closed-source. Cannot use.** Documented for completeness.

## Gemini Robotics 1.5 / ER 1.5 (DeepMind)

- **ER 1.5**: API-only embodied-reasoning VLM. No fine-tuning, no on-device.
- **Full Gemini Robotics 1.5 VLA**: partner-only, not publicly accessible.
- **Cannot use.** Documented for completeness.

## Generalization analysis (GR00T only)

| Axis | Generalizes? | Notes |
|---|---|---|
| NIC index 0–4 | strong | Visual generalization from VLM pretraining. |
| Board pose & yaw | strong | Same. |
| Plug type | strong with text conditioning | Natural language goal. |
| Grasp-pose noise | moderate; needs F/T augmentation | Per 2512.01358 paper. |
| Sim-to-real | strong | Isaac-trained, designed for real. |

## Key resources

| Resource | Year | What |
|---|---|---|
| Bjorck et al., "GR00T N1" | 2025 | arXiv 2503.14734 |
| NVIDIA Isaac-GR00T | maintained | <https://github.com/NVIDIA/Isaac-GR00T> |
| GR00T N1.5 SO-101 LeRobot blog | 2025 | <https://huggingface.co/blog/nvidia/gr00t-n1-5-so101-tuning> |
| Helix (Figure blog) | 2025 | Closed; reference only. |
| Gemini Robotics 1.5 tech report | 2025 | DeepMind; partner-only. |
| Modality-Augmented GR00T (F/T) | 2025 | arXiv 2512.01358 |

## Data needs

- 50-500 demos for FT. Same as π0.
- Public pretraining handled.

## Compute & time

- **FT with `--no-tune_diffusion_model`**: ~12-24 hours on 16 GB. Quality compromise.
- Inference: ~50-80 ms / chunk.

## Best simulation environment

GR00T is Isaac-native. Training in Isaac + eval-in-Gazebo introduces sim-to-sim risk (see [[rl-ppo-isaac]] file `09`).

## Auto-research applicability — **low**

Each iter is 12-24 hours; limited Karpathy fit.

## My note: top-30 probability — **low**

For AIC's narrow task scope and our 16 GB hardware, the **engineering cost / expected payoff ratio is worst** in the VLA family. **Prefer SmolVLA** (file `15`).

## Priority for our project — **5 of 5** (skip unless strategic reason)

Skip. Only revisit if Phase 1 (Flowstate) brings NVIDIA tooling integration as a strategic win.

## Cross-refs

- LeRobot VLA picks: [[vla-smolvla-pi0]] (file `15`).
- Other VLA options: [[vla-openvla]] (file `13`, skip), [[vla-octo]] (file `14`).
