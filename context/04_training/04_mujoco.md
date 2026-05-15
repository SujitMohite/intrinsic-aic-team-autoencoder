# MuJoCo Integration

Source: [`aic_utils/aic_mujoco/README.md`](../../aic_utils/aic_mujoco/README.md). DeepMind-prepared.

## What's provided

- Conversion utility to turn the Gazebo SDF world into MuJoCo MJCF.
- `aic_mujoco/scripts/add_cable_plugin.py` — post-processes the converted MJCF to add:
  - Motor actuators on each joint.
  - Gripper mimic constraint.
  - F/T sensor.
  - A `gripper_tcp` site.
  - Cable physics tuning.
  - Weld + contact exclusions.
- `aic_mujoco/launch/` ROS 2 launch files that bind MuJoCo to `ros2_control`, so our `aic_controller` interface works unchanged.

## Setup outline

1. `pixi install` already pulls `mujoco==3.5.0` (PyPI).
2. Convert: `python <mujoco script> --in /tmp/aic.sdf --out scene.mjcf` (see the script for exact flags).
3. Patch: `python aic_utils/aic_mujoco/scripts/add_cable_plugin.py scene.mjcf`.
4. Launch: `ros2 launch aic_mujoco aic_mujoco_bringup.launch.py` (or similar — check the README).

## When to use MuJoCo

- **Lighter than Gazebo**; faster than Isaac at single-env scale.
- **Contact model differs** — sometimes more forgiving for insertion, sometimes stiffer.
- **CPU-only friendly** — useful when GPU is busy training elsewhere.

## Cable physics

MuJoCo's cable plugin (composite body) is qualitatively similar to Gazebo's flexible cable, but bending stiffness, damping, and contact behaviour differ. **Don't expect identical scoring outcomes** between sims.

## Integration with our pipeline

- Record demos in MuJoCo via the same LeRobot teleop scripts.
- Mix MuJoCo data with Gazebo and Isaac in the AE pretraining set.
- Train a policy in MuJoCo and validate in Gazebo before submitting.

## Pitfalls

- The conversion is lossy. **The MJCF won't reproduce Gazebo's GI lighting** — visual policies trained on MuJoCo images may underperform when transferred. Mitigate via aggressive image augmentation.
- The cable plugin can deviate especially near tight constraints; insertion success thresholds may shift.
- `ros2_control` in MuJoCo runs at a configurable rate — ensure 500 Hz matches Gazebo if doing controller comparisons.

## Implication for our autoencoder

- Same as Isaac: pretrain the encoder on a mix of all three sims for visual robustness.
- Treat MuJoCo as a **cheap regression check** — `python -m team_autoencoder.run_mujoco_eval` can run dozens of trials a minute, useful CI.
