# Scene & Hardware

Source: [`docs/scene_description.md`](../../docs/scene_description.md), [`aic_description/`](../../aic_description/), [`aic_assets/`](../../aic_assets/).

## Robot

| Component | Spec |
| --- | --- |
| Arm | Universal Robots **UR5e** (6 DoF) |
| Gripper | **Robotiq Hand-E** (parallel jaw) |
| F/T sensor | ATI **AXIA80-M20** at the wrist |
| Cameras (3, wrist-mounted) | Basler **acA2440-20gc** with Edmunds 58-000 lens; **1152 × 1024** @ 20 FPS |

Robot description (URDF/xacro): [`aic_description/urdf/ur_gz.urdf.xacro`](../../aic_description/urdf/ur_gz.urdf.xacro).

## Cameras — coordinate frames & topics

| Camera | Image topic | Calibration topic |
| --- | --- | --- |
| Left | `/left_camera/image` | `/left_camera/camera_info` |
| Center | `/center_camera/image` | `/center_camera/camera_info` |
| Right | `/right_camera/image` | `/right_camera/camera_info` |

These are **already rectified**. CameraInfo gives K, D, P, etc.

## TCP frame

`gripper/tcp` — the "pinch point" between the gripper fingertips. This is what `MotionUpdate.pose` controls when `frame_id == "gripper/tcp"` (relative offset) or `"base_link"` (global pose).

## World

Gazebo world: [`aic_description/world/aic.sdf`](../../aic_description/world/aic.sdf). Includes:
- Floor
- Enclosure walls (transparent acrylic)
- Enclosure (structural frame: floor, corner posts, ceiling)
- Lighting
- A global-illumination plugin (disable for CPU-only via `<enabled>false</enabled>` if needed)
- A plugin that exports the world state to `/tmp/aic.sdf` after spawning

## Off-limit entities (collision = penalty)

| Model | Contents |
| --- | --- |
| `enclosure` | Floor, corner posts, ceiling |
| `enclosure walls` | Acrylic panels around the workspace |
| `task_board` | The board and **everything mounted on it** — NIC mounts, ports, etc. |

Only robot-link contacts trigger the penalty. The **cable itself is not penalized** for touching the board (it's a separate model).

## Force / sim time

- Sim runs at 1.0 real-time factor when GPU is healthy.
- F/T is **tared at startup** by the engine before our cable spawns — baseline ≈ 0 N for us.
- During eval, we cannot re-tare.

## Customizing the scene (training only)

```bash
/entrypoint.sh \
  spawn_task_board:=true \
  task_board_x:=0.3 task_board_y:=-0.1 task_board_z:=1.2 \
  task_board_yaw:=0.785 \
  nic_card_mount_2_present:=true \
  spawn_cable:=true cable_type:=sfp_sc_cable attach_cable_to_gripper:=true \
  ground_truth:=true start_aic_engine:=false
```

Full launch-arg list: [`aic_bringup/README.md`](../../aic_bringup/README.md).

After spawning, world state saves to `/tmp/aic.sdf` — copy to preserve a scenario:
```bash
cp /tmp/aic.sdf ~/training_scenarios/nic2_yaw45.sdf
```

## Programmatic respawn (training)

```bash
ros2 launch aic_training_utils aic_training_gz_bringup.launch.py
ros2 service call /expand_xacro aic_training_interfaces/srv/ExpandXacro \
  "{package_name: 'aic_description',
    relative_path: 'urdf/task_board.urdf.xacro',
    xacro_arguments: ['ground_truth:=true', 'nic_card_mount_0_present:=true']}"
```
Pipe the returned XML to `/gz_server/spawn_entity` for per-episode randomization.
