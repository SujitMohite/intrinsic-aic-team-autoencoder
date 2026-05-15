# Teleoperation & Data Collection

Source: [`aic_utils/aic_teleoperation/README.md`](../../aic_utils/aic_teleoperation/README.md), [`aic_utils/lerobot_robot_aic/`](../../aic_utils/lerobot_robot_aic/).

## Why teleop matters

For imitation learning (ACT, diffusion, our AE-policy head), we need **demonstrations** of successful insertions. The fastest path: teleop the simulator with the same scene the eval will randomize.

## Keyboard teleop (built-in)

Two modes, both in `aic_utils/aic_teleoperation/`:

### Joint-space
```
ros2 run aic_teleoperation joint_keyboard_teleop
```
- Keys: `q/a w/s e/d r/f t/g y/h` for joints 1–6
- `k/l` adjusts speed

### Cartesian-space
```
ros2 run aic_teleoperation cartesian_keyboard_teleop
```
- `a/d w/s r/f` for XYZ translation
- `Shift+s/Shift+w` pitch, `Shift+a/Shift+d` roll, `q/e` yaw
- `n/m` toggle frame (gripper/tcp vs base_link)
- `k/l` speed

## Setup before teleop

```bash
# Eval container running with start_aic_engine:=false (so we have free control)
/entrypoint.sh ground_truth:=true start_aic_engine:=false \
  spawn_task_board:=true spawn_cable:=true \
  attach_cable_to_gripper:=true cable_type:=sfp_sc_cable

# Tare F/T before each episode (NOT available during eval, but is during training)
ros2 service call /aic_controller/tare_force_torque_sensor std_srvs/srv/Trigger
```

## Recording

The LeRobot side of the toolkit provides recording via `lerobot_robot_aic`:

```bash
# Isaac Lab variant
python aic_utils/aic_isaac/aic_isaaclab/scripts/record_demos.py --task Insertion-v0

# LeRobot generic
lerobot-record \
  --robot.type=aic \
  --teleop.type=keyboard \
  --dataset.repo_id=team_autoencoder/aic_demos \
  --dataset.num_episodes=20
```

Output: parquet datasets compatible with LeRobot's training scripts.

## What to record

For our autoencoder pipeline:
- Camera images (all 3) → input to encoder.
- Joint states + F/T + controller state → ancillary modalities.
- Action stream (`MotionUpdate` / `JointMotionUpdate`) → supervision signal.
- Trial config (which NIC card, which port, board pose) → for sweep diversity.

## How many demos?

- ACT typically needs ~50–200 demos for tabletop manipulation.
- For our autoencoder pre-train, **any** rollouts (not necessarily successful) are useful, since the AE learns visual structure.

## Spacemouse / XR (Isaac Lab)

`aic_utils/aic_isaac` supports spacemouse and OpenXR teleop. If we have an HTC Vive / Quest, this is faster than keyboard for natural insertion motions.

## Practical: keyboard teleop strategy for SFP

1. Start with task board spawned and ground-truth on.
2. Press `b` (or whatever's bound) to slow speed.
3. Approach the NIC card from the side (NIC SFP ports face the user).
4. Visual-align in z to port height, then slide into the port.
5. Stop at first contact; let the controller's impedance settle.
6. Press the small forward nudge a few times to insert.
7. Record contact event + force spike.

Each demo: ~10–20 s at sim-real time.

## After recording

- Push the dataset to HuggingFace Hub (private) or store locally under `~/aic_datasets/`.
- Reference it from LeRobot training scripts (see [`02_lerobot.md`](./02_lerobot.md)).

## Pitfalls

- **Tare F/T before each episode.** Otherwise the recorded wrench has a meaningless bias.
- **Vary the task board pose / NIC index** during recording, otherwise the AE / policy overfits to one configuration.
- **Keep episodes short.** Long pauses while you think pollute the demo with non-task time. Use `/aic_controller/change_target_mode` to hold position when planning.
