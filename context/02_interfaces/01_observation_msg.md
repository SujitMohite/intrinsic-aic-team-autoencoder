# Observation Message

Definition: [`aic_interfaces/aic_model_interfaces/msg/Observation.msg`](../../aic_interfaces/aic_model_interfaces/msg/Observation.msg).

```
sensor_msgs/Image          left_image
sensor_msgs/CameraInfo     left_camera_info

sensor_msgs/Image          center_image
sensor_msgs/CameraInfo     center_camera_info

sensor_msgs/Image          right_image
sensor_msgs/CameraInfo     right_camera_info

geometry_msgs/WrenchStamped wrist_wrench

sensor_msgs/JointState      joint_states
aic_control_interfaces/ControllerState controller_state
```

Built by [`aic_adapter`](../../aic_adapter/), published on the `observations` topic at **20 Hz**.

## Fields, in order of usefulness for a policy

### Cameras

Three RGB cameras, all wrist-mounted, all rectified. **1152 × 1024**. Encoding usually `bgr8` (verify per topic — `Image.encoding`).

Why three? Stereo geometry from any two; the third gives the third axis (or redundancy / occlusion).

For us: each image is 3.5 MB raw. Downsample early. A typical autoencoder input would be 128–256 px.

### Wrist wrench

`geometry_msgs/WrenchStamped wrist_wrench` — 3D force + 3D torque at the wrist sensor.

- Tared once at start; readings should be ≈ 0 N at rest.
- Force-aware policies use this to detect contact and back off (force > 20 N for > 1 s → penalty).
- For us as an autoencoder team: useful auxiliary signal for the latent.

### Joint states

`sensor_msgs/JointState joint_states` — positions, velocities, efforts of the 6 UR5e joints. Use these instead of integrating `/tf` if you just need configuration.

### Controller state

`aic_control_interfaces/ControllerState controller_state` includes:
- Current TCP pose.
- Current TCP velocity.
- Reference / target TCP pose.
- Tracking error.
- Reference joint efforts.
- F/T tare offset.

This is the most direct source of "where the gripper is" without going through `/tf`.

## Accessing the latest observation in a Policy

```python
def insert_cable(self, task, get_observation, move_robot, send_feedback):
    obs = get_observation()                # blocking until first arrival
    img_left = obs.left_image              # sensor_msgs/Image
    wrench = obs.wrist_wrench.wrench
    joints = obs.joint_states.position
    tcp_pose = obs.controller_state.tcp_pose
    ...
```

`get_observation()` always returns the **most recent** Observation — not a queue. Run at whatever rate you like, but the adapter caps the producer at 20 Hz.

## Converting images for ML

```python
import cv2
import numpy as np

def img_to_np(msg):
    arr = np.frombuffer(msg.data, dtype=np.uint8)
    arr = arr.reshape(msg.height, msg.width, 3)
    return arr  # already BGR if encoding is 'bgr8'
```

We do NOT import `cv_bridge`; the lightweight raw-buffer approach is faster and avoids the dep.

## Pitfall: don't subscribe to raw camera topics inside the Policy

The aggregate is already time-synchronized for you. Subscribing to `/left_camera/image` directly costs another copy and breaks synchronization. **Use `obs.left_image`.**
