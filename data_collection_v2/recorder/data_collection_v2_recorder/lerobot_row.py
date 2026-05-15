"""Per-row builder. Converts an Observation + latest action snapshot into the
column dict the LeRobot v2 writer expects.

Schema reference: pipeline/lerobot_v2_writer.py (STATE_DIM, WRENCH_DIM, ACTION_DIM).
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


STATE_DIM = 25
WRENCH_DIM = 6
ACTION_DIM = 13


def image_to_jpg_bytes(img_msg, downsample_hw: tuple[int, int], quality: int) -> bytes:
    """sensor_msgs/Image -> JPG bytes, downsampled to downsample_hw.

    Returns empty bytes if the image is missing or zero-sized.
    """
    if not img_msg.data or img_msg.height == 0 or img_msg.width == 0:
        return b""
    arr = np.frombuffer(img_msg.data, dtype=np.uint8).reshape(
        img_msg.height, img_msg.width, 3
    )
    if img_msg.encoding == "rgb8":
        arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    h, w = downsample_hw
    if (img_msg.height, img_msg.width) != (h, w):
        arr = cv2.resize(arr, (w, h), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", arr, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    return bytes(buf) if ok else b""


def _stiffness_diag(flat36: list[float]) -> list[float]:
    """Extract the 6 diagonal entries of a row-major 6x6 matrix."""
    if not flat36 or len(flat36) < 36:
        return [0.0] * 6
    return [float(flat36[i * 6 + i]) for i in range(6)]


def _pad6(values, default: float = 0.0) -> list[float]:
    out = [float(v) for v in list(values)[:6]]
    while len(out) < 6:
        out.append(default)
    return out


def build_observation_state(obs) -> list[float]:
    """Return the 25-dim observation.state vector.

    Layout:
      tcp_pose (7)   : pos_xyz, ori_xyzw
      tcp_vel  (6)   : linear_xyz, angular_xyz
      joint_pos (6)  : UR5e joint positions (first 6)
      joint_vel (6)  : UR5e joint velocities (first 6)
    """
    cs = obs.controller_state
    p = cs.tcp_pose.position
    o = cs.tcp_pose.orientation
    vl = cs.tcp_velocity.linear
    va = cs.tcp_velocity.angular

    out: list[float] = [
        float(p.x), float(p.y), float(p.z),
        float(o.x), float(o.y), float(o.z), float(o.w),
        float(vl.x), float(vl.y), float(vl.z),
        float(va.x), float(va.y), float(va.z),
    ]
    out.extend(_pad6(obs.joint_states.position))
    out.extend(_pad6(obs.joint_states.velocity))
    return out


def build_observation_wrench(obs) -> list[float]:
    w = obs.wrist_wrench.wrench
    return [
        float(w.force.x), float(w.force.y), float(w.force.z),
        float(w.torque.x), float(w.torque.y), float(w.torque.z),
    ]


def build_action(motion_msg, joint_msg, last_topic: str | None) -> list[float]:
    """Return the 13-dim action vector.

    Layout:
      twist_lin (3)
      twist_ang (3)
      stiffness_diag (6) — diagonal of the 6x6 stiffness matrix
      traj_mode (1)

    If the most recent command was a JointMotionUpdate (rare under CheatCode),
    we surface the joint-mode stiffness diagonal and a zero twist. Twist values
    are 0 in joint mode because the controller resolves joint targets internally.
    """
    twist_lin = [0.0, 0.0, 0.0]
    twist_ang = [0.0, 0.0, 0.0]
    stiffness = [0.0] * 6
    traj_mode = 0.0

    if last_topic == "pose" and motion_msg is not None:
        twist_lin = [
            float(motion_msg.velocity.linear.x),
            float(motion_msg.velocity.linear.y),
            float(motion_msg.velocity.linear.z),
        ]
        twist_ang = [
            float(motion_msg.velocity.angular.x),
            float(motion_msg.velocity.angular.y),
            float(motion_msg.velocity.angular.z),
        ]
        stiffness = _stiffness_diag(list(motion_msg.target_stiffness))
        traj_mode = float(int(motion_msg.trajectory_generation_mode.mode))
    elif last_topic == "joint" and joint_msg is not None:
        # Joint-mode stiffness is already per-joint (6 values), no need to extract diag.
        stiff = list(joint_msg.target_stiffness)[:6]
        while len(stiff) < 6:
            stiff.append(0.0)
        stiffness = [float(v) for v in stiff]
        traj_mode = float(int(joint_msg.trajectory_generation_mode.mode))

    return twist_lin + twist_ang + stiffness + [traj_mode]


def build_row(
    obs,
    motion_msg,
    joint_msg,
    last_topic: str | None,
    frame_index: int,
    timestamp_sec: float,
    downsample_hw: tuple[int, int],
    jpg_quality: int,
) -> dict[str, Any]:
    """Compose one LeRobot v2 row from current observation + latest action.

    Fields filled in by the writer (NOT here):
      episode_index, task_index, index, next.done, next.success.
    """
    return {
        "observation.images.left": image_to_jpg_bytes(obs.left_image, downsample_hw, jpg_quality),
        "observation.images.center": image_to_jpg_bytes(obs.center_image, downsample_hw, jpg_quality),
        "observation.images.right": image_to_jpg_bytes(obs.right_image, downsample_hw, jpg_quality),
        "observation.state": [float(v) for v in build_observation_state(obs)],
        "observation.wrench": [float(v) for v in build_observation_wrench(obs)],
        "action": [float(v) for v in build_action(motion_msg, joint_msg, last_topic)],
        "timestamp": float(timestamp_sec),
        "frame_index": int(frame_index),
        "next.reward": 0.0,
        "_insertion_seen": False,
    }
