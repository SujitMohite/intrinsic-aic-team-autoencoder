"""rclpy recorder node.

Subscribes to:
  /aic_model/transition_event       trial boundary trigger
  /scoring/insertion_event          per-trial success marker
  /observations                     row driver (sensor data QoS, ~20 Hz)
  /aic_controller/pose_commands     latest pose action (held)
  /aic_controller/joint_commands    latest joint action (held)

Writes per-episode LeRobot v2 parquet via pipeline.lerobot_v2_writer.WriteSession,
appends a manifest row per episode, and finalizes meta files on shutdown.

Parameters:
  output_dir           absolute path to dataset root (lerobot_v2 layout sits inside)
  trial_configs        absolute path to <session>.yaml.trials.jsonl sidecar
  fps                  observation rate written into info.json (default 20)
  image_jpg_quality    JPG quality 0-100 (default 85)
  camera_h, camera_w   downsample target (defaults 256, 256)
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import rclpy
from aic_control_interfaces.msg import JointMotionUpdate, MotionUpdate
from aic_model_interfaces.msg import Observation
from lifecycle_msgs.msg import TransitionEvent
from rclpy.node import Node
from rclpy.qos import QoSPresetProfiles
from std_msgs.msg import String

# Inject the repo root onto sys.path so we can import data_collection_v2.pipeline.*
# without packaging it as a ROS 2 package. parents[3] from this file resolves to
# .../intrinsic-aic-team-autoencoder/ (the repo root), since the file lives at
# <repo_root>/data_collection_v2/recorder/data_collection_v2_recorder/recorder_node.py.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from data_collection_v2.pipeline.lerobot_v2_writer import WriteSession  # noqa: E402
from data_collection_v2.pipeline.manifest import Manifest  # noqa: E402

from .boundary_detector import (  # noqa: E402
    BoundaryDetector,
    PRIMARY_STATE_ACTIVE,
    PRIMARY_STATE_INACTIVE,
)
from .lerobot_row import build_row  # noqa: E402


_LOG = logging.getLogger("recorder.node")


def _load_sidecar(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"trial_configs sidecar not found: {path}")
    out: list[dict[str, Any]] = []
    with open(path) as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            out.append(json.loads(ln))
    return out


class RecorderNode(Node):
    def __init__(self) -> None:
        super().__init__("aic_data_recorder_v2")

        self.declare_parameter("output_dir", "")
        self.declare_parameter("trial_configs", "")
        self.declare_parameter("fps", 20)
        self.declare_parameter("image_jpg_quality", 85)
        self.declare_parameter("camera_h", 256)
        self.declare_parameter("camera_w", 256)

        output_dir = self.get_parameter("output_dir").get_parameter_value().string_value
        trial_configs_path = (
            self.get_parameter("trial_configs").get_parameter_value().string_value
        )
        self._fps = int(self.get_parameter("fps").value)
        self._jpg_q = int(self.get_parameter("image_jpg_quality").value)
        self._camera_hw = (
            int(self.get_parameter("camera_h").value),
            int(self.get_parameter("camera_w").value),
        )

        if not output_dir:
            raise RuntimeError("output_dir parameter is required")
        if not trial_configs_path:
            raise RuntimeError("trial_configs parameter is required")

        self._root = Path(output_dir)
        self._root.mkdir(parents=True, exist_ok=True)
        self._dataset = WriteSession(
            root=self._root / "lerobot_v2",
            fps=self._fps,
            camera_hw=self._camera_hw,
        )
        self._manifest = Manifest(self._root / "manifest.jsonl")
        self._sidecar = _load_sidecar(Path(trial_configs_path))
        self.get_logger().info(
            f"recorder: output_dir={self._root} sidecar={len(self._sidecar)} trials"
        )

        # Recording buffers.
        self._rows: list[dict[str, Any]] = []
        self._ep_start_sim_ns: int | None = None
        self._current_trial: dict[str, Any] | None = None
        self._pending_insertion_event = False
        self._latest_motion: MotionUpdate | None = None
        self._latest_joint: JointMotionUpdate | None = None
        self._latest_topic: str | None = None
        self._frame_index = 0

        # Boundary state machine.
        self._boundary = BoundaryDetector(
            on_trial_start=self._handle_trial_start,
            on_trial_end=self._handle_trial_end,
        )

        # Subscriptions.
        qos_sensor = QoSPresetProfiles.SENSOR_DATA.value
        qos_default = QoSPresetProfiles.SYSTEM_DEFAULT.value

        self.create_subscription(
            TransitionEvent,
            "/aic_model/transition_event",
            self._on_transition,
            qos_default,
        )
        self.create_subscription(
            String, "/scoring/insertion_event", self._on_insertion, qos_default
        )
        self.create_subscription(
            Observation, "/observations", self._on_observation, qos_sensor
        )
        self.create_subscription(
            MotionUpdate,
            "/aic_controller/pose_commands",
            self._on_pose_cmd,
            qos_default,
        )
        self.create_subscription(
            JointMotionUpdate,
            "/aic_controller/joint_commands",
            self._on_joint_cmd,
            qos_default,
        )

        self.get_logger().info("recorder ready: waiting for /aic_model transitions")

    # ---- ROS callbacks ----

    def _on_transition(self, msg: TransitionEvent) -> None:
        self._boundary.handle_transition(
            int(msg.goal_state.id), str(msg.goal_state.label)
        )

    def _on_insertion(self, msg: String) -> None:
        if self._boundary.current_trial_index == 0:
            return
        self._pending_insertion_event = True
        self.get_logger().info(f"insertion_event seen: {msg.data!r}")

    def _on_pose_cmd(self, msg: MotionUpdate) -> None:
        self._latest_motion = msg
        self._latest_topic = "pose"

    def _on_joint_cmd(self, msg: JointMotionUpdate) -> None:
        self._latest_joint = msg
        self._latest_topic = "joint"

    def _on_observation(self, msg: Observation) -> None:
        if self._boundary.state.value != "recording":
            return
        sim_ns = (
            msg.joint_states.header.stamp.sec * 1_000_000_000
            + msg.joint_states.header.stamp.nanosec
        )
        if self._ep_start_sim_ns is None:
            self._ep_start_sim_ns = sim_ns
        ts = (sim_ns - self._ep_start_sim_ns) / 1e9

        row = build_row(
            obs=msg,
            motion_msg=self._latest_motion,
            joint_msg=self._latest_joint,
            last_topic=self._latest_topic,
            frame_index=self._frame_index,
            timestamp_sec=ts,
            downsample_hw=self._camera_hw,
            jpg_quality=self._jpg_q,
        )
        if self._pending_insertion_event:
            row["_insertion_seen"] = True
            row["next.reward"] = 1.0
            self._pending_insertion_event = False
        self._rows.append(row)
        self._frame_index += 1

    # ---- Boundary callbacks ----

    def _handle_trial_start(self, trial_index_1based: int) -> None:
        # Reset per-episode buffers BEFORE the recorder starts accepting rows.
        self._rows = []
        self._ep_start_sim_ns = None
        self._pending_insertion_event = False
        self._frame_index = 0

        # Look up the TrialConfig by 1-based trial index (matches engine order).
        idx0 = trial_index_1based - 1
        if 0 <= idx0 < len(self._sidecar):
            self._current_trial = self._sidecar[idx0]
        else:
            self.get_logger().warn(
                f"trial index {trial_index_1based} outside sidecar range "
                f"(have {len(self._sidecar)} trials)"
            )
            self._current_trial = None

    def _handle_trial_end(self) -> None:
        rows = self._rows
        trial = self._current_trial
        # Defensive: clear state immediately so a re-entrant transition doesn't
        # double-flush.
        self._rows = []
        self._current_trial = None
        self._ep_start_sim_ns = None
        self._pending_insertion_event = False
        self._frame_index = 0

        if not rows:
            self.get_logger().warn(
                "trial ended with 0 rows recorded — appending invalid manifest row"
            )
            self._append_manifest_row(trial=trial, ep_meta=None, n_rows=0)
            return

        tc = (trial or {}).get("trial_config", {}) or {}
        task = f"{tc.get('plug_type', 'unknown')}_insertion"
        try:
            ep_meta = self._dataset.write_episode(rows=rows, task=task)
        except Exception as e:  # noqa: BLE001
            self.get_logger().error(f"parquet write failed: {e}")
            self._append_manifest_row(trial=trial, ep_meta=None, n_rows=len(rows))
            return
        self._append_manifest_row(trial=trial, ep_meta=ep_meta, n_rows=len(rows))

    # ---- Manifest ----

    def _append_manifest_row(
        self,
        trial: dict[str, Any] | None,
        ep_meta: dict[str, Any] | None,
        n_rows: int,
    ) -> None:
        tc = (trial or {}).get("trial_config", {}) or {}
        row = {
            "ep_id": tc.get("ep_id"),
            "seed": tc.get("seed"),
            "trial_index_1based": self._boundary.current_trial_index,
            "trial_key": (trial or {}).get("trial_key"),
            "trial_config": tc,
            "n_rows": int(n_rows),
            "episode_index": (ep_meta or {}).get("episode_index"),
            "parquet_path": (ep_meta or {}).get("parquet_path"),
            "task": (ep_meta or {}).get("task"),
            # Scoring is backfilled at session finalization from the engine's
            # session-end scoring.yaml. Until then, valid/scoring stay null.
            "valid": None,
            "scoring": None,
        }
        self._manifest.append(row)

    # ---- Shutdown ----

    def finalize(self) -> None:
        try:
            self._dataset.finalize()
        except Exception as e:  # noqa: BLE001
            self.get_logger().error(f"dataset finalize failed: {e}")


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = RecorderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.finalize()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
