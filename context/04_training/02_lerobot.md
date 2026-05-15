# LeRobot Integration

Sources: [`aic_utils/lerobot_robot_aic/`](../../aic_utils/lerobot_robot_aic/), `aic_example_policies/aic_example_policies/ros/RunACT.py`, root `pixi.toml`.

## What's wired in

`pixi.toml` pins:
- `lerobot==0.5.1` (PyPI)
- `lerobot_robot_ros` (git fork by koonpeng — `subdirectory=lerobot_robot_ros`)
- `lerobot_teleoperator_devices` (same fork)
- ROS-side adapter: `ros-kilted-lerobot-robot-aic = { path = "aic_utils/lerobot_robot_aic" }`

## Why LeRobot

LeRobot is HuggingFace's open-source robot-learning stack:
- Datasets schema (parquet) and Hub upload.
- Training scripts for **ACT**, **Diffusion Policy**, **Pi0**, others.
- Inference runtime.

The `lerobot_robot_aic` package is the **ROS bridge**: it implements LeRobot's `Robot` interface against our `/aic_controller` topics + Observation aggregate, so LeRobot scripts can record / replay / control our sim transparently.

## Typical workflow

1. **Record demos** with teleop + LeRobot:
   ```bash
   lerobot-record --robot.type=aic --teleop.type=keyboard \
     --dataset.repo_id=team_autoencoder/aic_demos --dataset.num_episodes=50
   ```
2. **Train** (LeRobot's `lerobot-train`):
   ```bash
   lerobot-train --policy.type=act --dataset.repo_id=team_autoencoder/aic_demos \
     --output.dir=outputs/act_aic_v1 --training.steps=200000
   ```
3. **Evaluate** by loading the checkpoint inside our policy class (same pattern as `RunACT.py`).

## RunACT — the reference

`aic_example_policies/aic_example_policies/ros/RunACT.py` shows:
- Lazy `import torch` etc. inside `insert_cable()`.
- `huggingface_hub.snapshot_download(...)` to fetch a checkpoint at runtime.
- Image decode via OpenCV.
- Conversion from LeRobot action tensors to `MotionUpdate` messages.
- `draccus` config glue.

For our submission to be reproducible, **bake the checkpoint into the Docker image** rather than downloading from HF Hub at runtime (the eval cloud may not have network egress).

## Where the autoencoder fits

Two integration patterns:

### A. AE as preprocessor

```
images ─► our autoencoder ─► latent ─┐
                                     ├─► ACT (or smaller MLP) ─► actions
F/T, joints ─────────────────────────┘
```

Train AE first (unsupervised on rollouts), then train the action head with ACT-style supervision from demos. Submit a class that holds both modules.

### B. AE as auxiliary loss

Train a policy directly (à la ACT) but add a reconstruction loss to the backbone of the vision encoder. Often more stable than pure supervised.

### C. Goal-conditioned AE

Encode (current_image, target_port_name) into a single latent. Force reconstruction to attend to the target port region — gives implicit attention.

We're deciding between these in [`../07_team/00_approach.md`](../07_team/00_approach.md).

## Action representation choice

LeRobot wants a fixed-length action vector per timestep. For our case:
- **Cartesian delta** `[dx, dy, dz, droll, dpitch, dyaw]` (6-dim) is concise and matches what the impedance controller expects with `gripper/tcp` frame.
- **Joint targets** (6-dim) trade portability for precision near singularities.

ACT outputs **chunks** of actions (e.g. 16-step chunks) — we publish them at 10–20 Hz inside `insert_cable()`.

## Dataset hygiene

- Use the SAME observation pipeline at training and inference time. The `Observation` aggregate is already synchronized; don't introduce a different image preprocessor in inference.
- Strip the trial id / Task before training, but keep `port_name` / `plug_type` if conditioning.
- Store a small subset (10 episodes) of *unsuccessful* demos too — they expose the failure boundary to the policy.

## Pitfall

LeRobot's `lerobot_robot_ros` fork is **not in the eval container by default**. It's installed in our pixi env on the host. Our submission Dockerfile pulls in `aic_utils/lerobot_robot_aic` and `lerobot==0.5.1` via the lockfile — no extra steps if we use the provided `docker/aic_model/Dockerfile` as the base.
