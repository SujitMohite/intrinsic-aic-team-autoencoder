# Isaac Lab Integration

Source: [`aic_utils/aic_isaac/README.md`](../../aic_utils/aic_isaac/README.md). NVIDIA-prepared.

## What's provided

- `aic_isaaclab/` Python package: AIC task / agent / asset files for Isaac Lab.
- Scripts:
  - `teleop.py` — keyboard / spacemouse / XR teleop in Isaac.
  - `record_demos.py` — episode recording in Isaac.
  - `replay_demos.py` — replay recorded demos.
  - `rsl_rl/train.py` and `rsl_rl/play.py` — RL training via RSL-RL.
- An NVIDIA-prepared asset pack (`Intrinsic_assets`).

## When to use Isaac

- **Massive parallel rollouts** for RL or large-scale demo generation. Isaac runs hundreds–thousands of envs on a single L4.
- **Better physics for some contact regimes** (NVIDIA PhysX, contact-rich tuned).
- **Domain randomization** to harden against Gazebo-specific quirks.

## Setup outline

Follow the upstream `aic_utils/aic_isaac/README.md` exactly — it's NVIDIA-maintained and changes over time. High-level:

1. Install Isaac Lab (standalone Conda env, NOT inside our pixi env).
2. Drop the AIC asset pack into the Isaac Lab assets path.
3. `isaaclab.sh -p record_demos.py --task ...` to collect demos.
4. Or `rsl_rl/train.py --task ...` for RL.

## RL with RSL-RL (rough sketch)

```bash
python aic_utils/aic_isaac/aic_isaaclab/scripts/rsl_rl/train.py \
  --task AIC-Insertion-SFP-v0 --headless --num_envs 1024
```

Policy outputs (joint targets or Cartesian deltas) trained against a shaped reward (proximity + insertion event).

To run trained policy in Gazebo eval, we extract the actor net and load it in our `Policy.insert_cable()` (lazy import torch, run inference per obs).

## What we cannot bring back

- Isaac's particular contact dynamics → trained policy may be overconfident in pushes Gazebo penalizes.
- **Mitigation:** train in Isaac with randomized stiffness / damping / friction, OR fine-tune in Gazebo using a small dataset of failures.

## Implication for our autoencoder

- Isaac's wrist-camera images **look different** from Gazebo's (lighting, materials). The AE pretrained on one will not transfer cleanly to the other.
- **Best practice:** pre-train AE on a mix of Gazebo + Isaac + MuJoCo rollouts (visual domain randomization) so the latent is invariant to renderer quirks.
- Alternative: pre-train per-simulator AEs and route at inference based on … wait, we won't know which simulator we're in. So mix.

## Cost

Isaac is heavyweight. Don't try to install it inside our pixi env; it has its own ecosystem (Conda + Omniverse Kit). Treat it as a separate workstation tool and copy data / checkpoints across.

## Verifying transfer

Before submitting an Isaac-trained policy: always run **at least one full 3-trial eval in Gazebo** to confirm Tier 1 + Tier 3 still pass.
