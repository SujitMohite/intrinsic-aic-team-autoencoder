# Motion Messages

Definitions:
- [`aic_control_interfaces/msg/MotionUpdate.msg`](../../aic_interfaces/aic_control_interfaces/msg/MotionUpdate.msg)
- [`aic_control_interfaces/msg/JointMotionUpdate.msg`](../../aic_interfaces/aic_control_interfaces/msg/JointMotionUpdate.msg)
- [`aic_control_interfaces/msg/TrajectoryGenerationMode.msg`](../../aic_interfaces/aic_control_interfaces/msg/TrajectoryGenerationMode.msg)

## MotionUpdate (Cartesian)

```
std_msgs/Header           header             # frame_id: "base_link" or "gripper/tcp"
geometry_msgs/Pose        pose               # target TCP pose (when MODE_POSITION)
geometry_msgs/Twist       velocity           # target TCP velocity (when MODE_VELOCITY)
float64[36]               target_stiffness   # 6x6, row-major
float64[36]               target_damping     # 6x6, row-major
geometry_msgs/Wrench      feedforward_wrench_at_tip  # optional ff force/torque at TCP
float64[6]                wrench_feedback_gains_at_tip  # 0..0.95 per dof
TrajectoryGenerationMode  trajectory_generation_mode    # MODE_POSITION (2) | MODE_VELOCITY (1)
```

### `frame_id` semantics

- `"base_link"` → `pose` is **absolute** in the robot base frame.
- `"gripper/tcp"` → `pose` is an **offset** from the current TCP. Same for velocity.

### Stiffness & damping intuition

| Behaviour | Stiffness (diag) | Damping (diag) |
| --- | --- | --- |
| Free-floating | ≈ 0 | ≈ 0 |
| Compliant follow | low (≈ 30) | low |
| Default `set_pose_target` | `[90, 90, 90, 50, 50, 50]` | `[50, 50, 50, 20, 20, 20]` |
| Aggressive snap (high jerk → penalty) | high (≥ 150) | low |
| Smooth gentle | moderate (60–80) | high (60–80) |

`set_pose_target` in `aic_model.policy.Policy` populates these for us. Override when we need different compliance.

### Trajectory generation mode

| Constant | Value | Effect |
| --- | --- | --- |
| `MODE_POSITION` | 2 | Follow `pose`; ignores `velocity` |
| `MODE_VELOCITY` | 1 | Follow `velocity`; ignores `pose` |

Confusing detail: enum value 1 is velocity, 2 is position. The `Policy.set_pose_target` helper sets `MODE_POSITION` for you.

### Wrench feedback gains

`wrench_feedback_gains_at_tip` is a 6-vector in [0, 0.95]. Higher = more impedance compliance to external force/torque. Defaults of `[0.5, 0.5, 0.5, 0, 0, 0]` give force compliance, no torque compliance — useful for insertions.

## JointMotionUpdate (Joint)

```
trajectory_msgs/JointTrajectoryPoint target_state  # positions/velocities/accels/efforts (6 each)
float64[]                target_stiffness          # per-joint
float64[]                target_damping            # per-joint
float64[]                target_feedforward_torque
TrajectoryGenerationMode trajectory_generation_mode
```

For our UR5e the array size is 6. Joint order from the URDF: `shoulder_pan_joint`, `shoulder_lift_joint`, `elbow_joint`, `wrist_1_joint`, `wrist_2_joint`, `wrist_3_joint`.

## Mode switching

Before sending the first JointMotionUpdate, call:
```python
ros2 service call /aic_controller/change_target_mode \
  aic_control_interfaces/srv/ChangeTargetMode "{target_mode: {mode: 2}}"
```
where `mode: 1` = Cartesian, `mode: 2` = Joint.

The `aic_model.move_robot()` callback **handles mode-switching automatically** when our policy sends a `JointMotionUpdate` or `MotionUpdate`. See `aic_model/aic_model.py:204-229`.

## Publication rate

The controller smooths and interpolates between commands, so a policy can publish at ~10–30 Hz and let the 500 Hz inner loop track. There's no hard upper rate, but spamming > 100 Hz adds nothing.

## Pitfalls

- **Stiffness must be a 6×6 matrix (row-major flat 36-array), not a 6-vector.** Use `np.diag([...]).flatten()`.
- **JointMotionUpdate stiffness is a 6-vector**, not 36. Different convention.
- **`header.stamp` must be the current sim time**: `header.stamp = self._parent_node.get_clock().now().to_msg()`.
- **Sending both** `motion_update` and `joint_motion_update` in the same call raises. The `move_robot` callback enforces XOR.
