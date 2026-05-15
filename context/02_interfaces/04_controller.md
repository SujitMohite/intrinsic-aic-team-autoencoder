# Controller

Source: [`docs/aic_controller.md`](../../docs/aic_controller.md), [`aic_controller/`](../../aic_controller/).

## What it is

A Cartesian and joint **impedance controller** for ROS 2. Receives our policy commands at ~10–30 Hz, runs an inner loop at ~500 Hz on the robot, and outputs torques.

```
policy --(MotionUpdate / JointMotionUpdate ~10-30 Hz)--> aic_controller --(joint torques @ ~500 Hz)--> robot
```

## Pipeline

1. **Clamping** — joint targets to URDF limits, Cartesian to user params.
2. **Interpolation** — smooths slow policy commands into high-rate setpoints.
3. **Impedance** — either CartesianImpedanceAction or JointImpedanceAction.
4. **Gravity compensation** — adds torque to counter gravity per link.
5. **Sum & ship** to joint actuators.

If tracking error stays large for too long (set by `tracking_error` in `aic_bringup/config/aic_ros2_controllers.yaml`), the controller **resets the target** — this prevents the "robot in collision with sticky accumulated error" trap.

## Modes

- **Cartesian** (default). Listens on `/aic_controller/pose_commands`.
- **Joint**. Listens on `/aic_controller/joint_commands`.

Switch:
```bash
# mode 1 = Cartesian, mode 2 = Joint
ros2 service call /aic_controller/change_target_mode \
  aic_control_interfaces/srv/ChangeTargetMode "{target_mode: {mode: 1}}"
```

`aic_model.move_robot()` does this automatically on first command of the new type.

## Cartesian impedance (math)

$$
\tau = J^T \big[ K_p (x_{des} - x) + K_d (\dot x_{des} - \dot x) + W_f \big] + \tau_{null}
$$

- $K_p$, $K_d$ are 6×6 (our `target_stiffness` / `target_damping`).
- $W_f$ is `feedforward_wrench_at_tip`.
- $\tau_{null}$ is internal (joint-limit avoidance, secondary tasks).

## Joint impedance (math)

$$
\tau = K_p (q_{des} - q) + K_d (\dot q_{des} - \dot q) + \tau_f
$$

- $K_p$, $K_d$ are 6-vectors here (one per joint).
- $\tau_f$ is `target_feedforward_torque`.

## Controller state telemetry

`/aic_controller/controller_state` (`aic_control_interfaces/ControllerState`) publishes:
- Current TCP pose & velocity.
- Reference (target) TCP pose.
- Tracking error.
- Reference joint efforts.
- `fts_tare_offset` (so we know the bias).

This is mirrored into `obs.controller_state` in the aggregate.

## Tare service

```bash
ros2 service call /aic_controller/tare_force_torque_sensor std_srvs/srv/Trigger
```

- **Available during training** (and the engine uses it pre-trial to zero F/T before spawning the cable).
- **Disabled at evaluation** for the policy. We rely on the engine's tare.

## What we cannot change

The controller config is **fixed** during evaluation. All teams use the same `aic_ros2_controllers.yaml`. So we cannot tune the inner-loop gains — only the per-command `target_stiffness` / `target_damping` we send.

## Practical tuning tips

| Goal | Try |
| --- | --- |
| Smooth approach (good jerk score) | Stiffness 60–90, damping 50–80 |
| Compliant final insertion | Drop stiffness in z (insertion axis) to ~30; keep xy stiff |
| Light contact force | `feedforward_wrench_at_tip = (0,0,-2)` (gentle pull toward port), `wrench_feedback_gains_at_tip[0..2] = 0.5` |
| Hold pose after success | Send the same `MotionUpdate` with MODE_POSITION and zero ff wrench |

## Implication for our policy

- A learned residual on top of a compliant impedance setpoint is usually safer than full-position command sequences.
- F/T-driven correction is cheap with the right wrench feedback gains; consider exposing the F/T into our autoencoder's latent.
