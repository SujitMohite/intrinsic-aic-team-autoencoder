"""Forked CheatCode with early-exit, used only for data collection.

Upstream `aic_example_policies.ros.CheatCode` runs its scripted descent for the
full per_trial_time_limit_s and then sleeps 5 s sim regardless of whether the
cable is already inserted. In the smoke log
(`/tmp/aic_v2_smoke/logs/session_20260514T202819Z.log`) the cable reaches the
Gazebo CablePlugin COMPLETED state at sim time ~24 s but the action does not
report success until sim ~60 s — at RTF 0.27 that is ~100 s of wall-clock
per-trial of pure no-op.

FastCheatCode keeps the approach + descent math identical (same data
distribution) but exits the descent loop as soon as either:
  1. `/scoring/insertion_event` fires (primary — emitted by ScoringTier2 when
     the engine confirms insertion), or
  2. plug_tip is co-located with port (|xy| < 2 mm, |dz| < 1 mm) for 3
     consecutive descent iterations (TF fallback, no scoring dependency).

The 5 s sim stabilize sleep is dropped on signal (1) and reduced to 0.5 s on
signal (2).
"""

from __future__ import annotations

import numpy as np

from aic_example_policies.ros.CheatCode import CheatCode
from aic_model.policy import (
    GetObservationCallback,
    MoveRobotCallback,
    SendFeedbackCallback,
)
from aic_model_interfaces.msg import Observation  # noqa: F401  (kept for parity)
from aic_task_interfaces.msg import Task
from geometry_msgs.msg import Pose  # noqa: F401  (kept for parity)
from rclpy.qos import QoSPresetProfiles
from rclpy.time import Time
from std_msgs.msg import String
from tf2_ros import TransformException


# Tunables — keep conservative; only the descent-tail behavior changes.
_TF_XY_TOL_M = 0.002
_TF_DZ_TOL_M = 0.001
_TF_CONSEC_HITS_REQUIRED = 3
_POST_EXIT_SETTLE_S = 0.5  # only used on TF-fallback exit


class FastCheatCode(CheatCode):
    def __init__(self, parent_node):
        super().__init__(parent_node)
        self._insertion_seen = False
        # Subscribe once; the topic persists across trials in the same container.
        self._parent_node.create_subscription(
            String,
            "/scoring/insertion_event",
            self._on_insertion_event,
            QoSPresetProfiles.SYSTEM_DEFAULT.value,
        )
        self.get_logger().info(
            "FastCheatCode ready (subscribed to /scoring/insertion_event)"
        )

    def _on_insertion_event(self, msg: String) -> None:
        self._insertion_seen = True
        self.get_logger().info(f"FastCheatCode: insertion_event={msg.data!r}")

    def _plug_tip_in_port(self, port_transform) -> bool:
        try:
            plug_tf = self._parent_node._tf_buffer.lookup_transform(
                "base_link",
                f"{self._task.cable_name}/{self._task.plug_name}_link",
                Time(),
            )
        except TransformException:
            return False
        dx = port_transform.translation.x - plug_tf.transform.translation.x
        dy = port_transform.translation.y - plug_tf.transform.translation.y
        dz = port_transform.translation.z - plug_tf.transform.translation.z
        return (
            abs(dx) < _TF_XY_TOL_M
            and abs(dy) < _TF_XY_TOL_M
            and abs(dz) < _TF_DZ_TOL_M
        )

    def insert_cable(
        self,
        task: Task,
        get_observation: GetObservationCallback,
        move_robot: MoveRobotCallback,
        send_feedback: SendFeedbackCallback,
    ):
        self.get_logger().info(f"FastCheatCode.insert_cable() task: {task}")
        self._task = task
        # Reset trial-scoped state. Events received before this point (e.g. from
        # a previous trial's reset window) must not trigger an early exit here.
        self._insertion_seen = False

        port_frame = f"task_board/{task.target_module_name}/{task.port_name}_link"
        cable_tip_frame = f"{task.cable_name}/{task.plug_name}_link"

        for frame in [port_frame, cable_tip_frame]:
            if not self._wait_for_tf("base_link", frame):
                return False

        try:
            port_tf_stamped = self._parent_node._tf_buffer.lookup_transform(
                "base_link",
                port_frame,
                Time(),
            )
        except TransformException as ex:
            self.get_logger().error(f"Could not look up port transform: {ex}")
            return False
        port_transform = port_tf_stamped.transform

        z_offset = 0.2

        # Approach phase — unchanged from CheatCode (5 s sim).
        for t in range(0, 100):
            interp_fraction = t / 100.0
            try:
                self.set_pose_target(
                    move_robot=move_robot,
                    pose=self.calc_gripper_pose(
                        port_transform,
                        slerp_fraction=interp_fraction,
                        position_fraction=interp_fraction,
                        z_offset=z_offset,
                        reset_xy_integrator=True,
                    ),
                )
            except TransformException as ex:
                self.get_logger().warn(f"TF lookup failed during interpolation: {ex}")
            self.sleep_for(0.05)

        # Descent + early-exit. Same descent dynamics as CheatCode (0.0005 m/step,
        # sleep 0.05 s sim) so the recorded action distribution is identical until
        # the moment we early-exit.
        descent_start_sim = self.time_now()
        tf_consec_hits = 0
        exit_source = None
        while True:
            if z_offset < -0.015:
                exit_source = "z_threshold"
                break
            if self._insertion_seen:
                exit_source = "insertion_event"
                break
            if self._plug_tip_in_port(port_transform):
                tf_consec_hits += 1
                if tf_consec_hits >= _TF_CONSEC_HITS_REQUIRED:
                    exit_source = "tf_fallback"
                    break
            else:
                tf_consec_hits = 0

            z_offset -= 0.0005
            try:
                self.set_pose_target(
                    move_robot=move_robot,
                    pose=self.calc_gripper_pose(port_transform, z_offset=z_offset),
                )
            except TransformException as ex:
                self.get_logger().warn(f"TF lookup failed during insertion: {ex}")
            self.sleep_for(0.05)

        descent_dur_sim = (self.time_now() - descent_start_sim).nanoseconds / 1e9
        self.get_logger().info(
            f"FastCheatCode early-exit: source={exit_source} "
            f"descent_sim_s={descent_dur_sim:.2f} final_z_offset={z_offset:.4f}"
        )

        # Stabilize. Only the z_threshold path mirrors upstream's 5 s wait — and
        # even there we shorten it, because by the time z_offset < -0.015 the
        # cable has been "pushed" for 15 mm beyond port_z and any remaining
        # motion is the controller damping out. On insertion_event we exit
        # immediately (engine has already scored); on tf_fallback we give the
        # controller a short settle window.
        if exit_source == "insertion_event":
            pass
        elif exit_source == "tf_fallback":
            self.sleep_for(_POST_EXIT_SETTLE_S)
        else:
            self.sleep_for(_POST_EXIT_SETTLE_S)

        self.get_logger().info("FastCheatCode.insert_cable() exiting...")
        return True
