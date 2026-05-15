# Topic Inventory

Source of truth: [`docs/aic_interfaces.md`](../../docs/aic_interfaces.md), the message definitions under [`aic_interfaces/`](../../aic_interfaces/).

## Inputs (we subscribe / consume)

### Sensor topics

| Topic | Msg type | Notes |
| --- | --- | --- |
| `/left_camera/image` | `sensor_msgs/Image` | Rectified, 1152×1024 @ 20 FPS |
| `/left_camera/camera_info` | `sensor_msgs/CameraInfo` | K, D, P |
| `/center_camera/image` | `sensor_msgs/Image` | Same |
| `/center_camera/camera_info` | `sensor_msgs/CameraInfo` | Same |
| `/right_camera/image` | `sensor_msgs/Image` | Same |
| `/right_camera/camera_info` | `sensor_msgs/CameraInfo` | Same |
| `/fts_broadcaster/wrench` | `geometry_msgs/WrenchStamped` | Tared at startup |
| `/joint_states` | `sensor_msgs/JointState` | UR5e joints |
| `/gripper_state` | `sensor_msgs/JointState` | Hand-E |
| `/tf` | `tf2_msgs/TFMessage` | Robot kinematics |
| `/tf_static` | `tf2_msgs/TFMessage` | URDF static frames |
| `/aic_controller/controller_state` | `aic_control_interfaces/ControllerState` | TCP pose/vel, ref pose, tracking error |

### Convenience aggregate

| Topic | Msg type | Notes |
| --- | --- | --- |
| `observations` | `aic_model_interfaces/Observation` | Time-synced bundle of all 3 cameras + F/T + joint_states + controller_state, **published at 20 Hz** by `aic_adapter`. **This is the single subscription that matters in the Policy class.** |

### Action server (consumed by us)

| Action | Type | Notes |
| --- | --- | --- |
| `/insert_cable` | `aic_task_interfaces/InsertCable` | Goal = Task, Feedback = string, Result = (success, message) |

## Outputs (we publish / produce)

### Robot commands

| Topic | Msg type | When |
| --- | --- | --- |
| `/aic_controller/pose_commands` | `aic_control_interfaces/MotionUpdate` | Controller mode = Cartesian (1) |
| `/aic_controller/joint_commands` | `aic_control_interfaces/JointMotionUpdate` | Controller mode = Joint (2) |

**Only one mode active at a time.** Switch via `/aic_controller/change_target_mode`.

### Services (we call)

| Service | Type | When |
| --- | --- | --- |
| `/aic_controller/change_target_mode` | `aic_control_interfaces/ChangeTargetMode` | Before sending the first command of a new mode |
| `/expand_xacro` | `aic_training_interfaces/ExpandXacro` | **Training only** — for programmatic spawning |
| `/aic_controller/tare_force_torque_sensor` | `std_srvs/Trigger` | **Training only** — disabled at eval |

## Off-limits (mentioned to make rules explicit)

Don't subscribe, don't publish, don't service-call:

- `/scoring/*` — anything under the scoring namespace, including `/scoring/tf` (ground-truth poses)
- `/gazebo/*`, `/gz_server/*` — simulator control plane
- `/clock` — don't override it (we **read** it via `use_sim_time:=true`, that's fine)
- `/model`, `/world_stats`, `/pause_physics`, world resets

Subscribing to `/tf` for general robot kinematics is fine. **Looking up port/plug ground-truth from `/scoring/tf` is not.**

## What `aic_model` sets up for us

When we run `ros2 run aic_model aic_model -p policy:=<our.policy>`:

- Subscribes to `observations` (the aggregate).
- Creates publishers for `/aic_controller/pose_commands` and `/aic_controller/joint_commands`.
- Creates an action server for `/insert_cable`.
- Wires lifecycle callbacks.
- Dynamically imports our policy module and instantiates the class.

So inside our `Policy.insert_cable()`, we get callbacks (`get_observation`, `move_robot`, `send_feedback`) — we usually never touch raw `rclpy` directly. See [`../03_policy/00_framework.md`](../03_policy/00_framework.md).
