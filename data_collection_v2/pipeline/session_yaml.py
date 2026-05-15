"""Render a multi-trial engine YAML for one collection session.

The engine reads N trials from `trials:` and iterates them in a single process
(aic_engine.cpp:583-615). v2 generates ONE session_<id>.yaml containing all N
pre-randomized trials, then starts the engine ONCE pointed at it. Between trials
the engine's native reset_after_trial path handles entity delete + joint home +
respawn — Gazebo and aic_model never restart.

Output:
  <out_path>                       — engine YAML (sample_config.yaml shape, N trials)
  <out_path>.trials.jsonl          — sidecar; one TrialConfig JSON per line in trial order

The recorder reads the sidecar to resolve trial_counter -> TrialConfig, avoiding
the need to parse the engine YAML inside the rclpy process.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

import yaml

from .config import TrialConfig


# Cable / plug → engine field mapping. Matches sample_config.yaml trial_1 (SFP)
# and trial_3 (SC) field shapes.
_PLUG_INFO = {
    "sfp": {
        "cable_name": "cable_0",
        "cable_type_in_cable_block": "sfp_sc_cable",
        "cable_type_in_task_block": "sfp_sc",
        "plug_name": "sfp_tip",
        # SFP grasps the SFP end; nominal gripper_offset from sample_config trial_1.
        "gripper_offset_y": 0.015385,
        "gripper_offset_z": 0.04245,
        "pose_roll": 0.4432,
        "pose_pitch": -0.4838,
        "pose_yaw": 1.3303,
    },
    "sc": {
        "cable_name": "cable_0",
        "cable_type_in_cable_block": "sfp_sc_cable_reversed",  # SC end gripped
        "cable_type_in_task_block": "sfp_sc",
        "plug_name": "sc_tip",
        # SC grasp uses sample_config trial_3 nominal gripper_offset.
        "gripper_offset_y": 0.015385,
        "gripper_offset_z": 0.04045,
        "pose_roll": 0.4432,
        "pose_pitch": -0.4838,
        "pose_yaw": 1.3303,
    },
}


# Auxiliary modules (lc_mount, sfp_mount, sc_mount) always present on the board.
# Fixed from sample_config trial_1 defaults — we don't randomize these in v2.
_AUX_MODULES_PRESENT = {
    "lc_mount_rail_0": {
        "entity_present": True,
        "entity_name": "lc_mount_0",
        "entity_pose": {"translation": 0.02, "roll": 0.0, "pitch": 0.0, "yaw": 0.0},
    },
    "sfp_mount_rail_0": {
        "entity_present": True,
        "entity_name": "sfp_mount_0",
        "entity_pose": {"translation": 0.03, "roll": 0.0, "pitch": 0.0, "yaw": 0.0},
    },
    "sc_mount_rail_0": {
        "entity_present": True,
        "entity_name": "sc_mount_0",
        "entity_pose": {"translation": -0.02, "roll": 0.0, "pitch": 0.0, "yaw": 0.0},
    },
    "lc_mount_rail_1": {
        "entity_present": True,
        "entity_name": "lc_mount_1",
        "entity_pose": {"translation": -0.01, "roll": 0.0, "pitch": 0.0, "yaw": 0.0},
    },
    "sfp_mount_rail_1": {"entity_present": False},
    "sc_mount_rail_1": {"entity_present": False},
}


def _build_trial_block(trial: TrialConfig) -> dict[str, Any]:
    info = _PLUG_INFO[trial.plug_type]
    cable_name = info["cable_name"]

    task_board: dict[str, Any] = {
        "pose": {
            "x": float(trial.task_board_x),
            "y": float(trial.task_board_y),
            "z": float(trial.task_board_z),
            "roll": 0.0,
            "pitch": 0.0,
            "yaw": float(trial.task_board_yaw),
        },
    }

    # NIC rails: only the chosen index is present for SFP, all absent for SC.
    for i in range(5):
        key = f"nic_rail_{i}"
        if trial.plug_type == "sfp" and trial.nic_card_index == i:
            task_board[key] = {
                "entity_present": True,
                "entity_name": f"nic_card_{i}",
                "entity_pose": {
                    "translation": float(trial.nic_rail_translation_m or 0.0),
                    "roll": 0.0,
                    "pitch": 0.0,
                    "yaw": float(trial.nic_card_yaw_offset_rad or 0.0),
                },
            }
        else:
            task_board[key] = {"entity_present": False}

    # SC rails: only the chosen index is present for SC, all absent for SFP.
    for i in range(2):
        key = f"sc_rail_{i}"
        if trial.plug_type == "sc" and trial.sc_rail == f"sc_rail_{i}":
            task_board[key] = {
                "entity_present": True,
                "entity_name": f"sc_mount_{i}",
                "entity_pose": {
                    "translation": float(trial.sc_rail_translation_m or 0.0),
                    "roll": 0.0,
                    "pitch": 0.0,
                    "yaw": 0.0,
                },
            }
        else:
            task_board[key] = {"entity_present": False}

    task_board.update(_AUX_MODULES_PRESENT)

    cables = {
        cable_name: {
            "pose": {
                "gripper_offset": {
                    "x": float(trial.grasp_offset_x),
                    "y": float(info["gripper_offset_y"]) + float(trial.grasp_offset_y),
                    "z": float(info["gripper_offset_z"]) + float(trial.grasp_offset_z),
                },
                "roll": float(info["pose_roll"]) + float(trial.grasp_offset_roll),
                "pitch": float(info["pose_pitch"]) + float(trial.grasp_offset_pitch),
                "yaw": float(info["pose_yaw"]) + float(trial.grasp_offset_yaw),
            },
            "attach_cable_to_gripper": True,
            "cable_type": info["cable_type_in_cable_block"],
        }
    }

    # Task block. SFP uses the per-trial port_name; SC uses the "sc_port_base"
    # alias (sample_config trial_3:324) and carries the actual port in target_module_name.
    port_name = trial.port_name if trial.plug_type == "sfp" else "sc_port_base"

    tasks = {
        "task_0": {
            "cable_type": info["cable_type_in_task_block"],
            "cable_name": cable_name,
            "plug_type": trial.plug_type,
            "plug_name": info["plug_name"],
            "port_type": trial.plug_type,
            "port_name": port_name,
            "target_module_name": trial.target_module_name,
            "time_limit": int(trial.time_limit_s),
        }
    }

    return {"scene": {"task_board": task_board, "cables": cables}, "tasks": tasks}


def _global_blocks_from_sample(sample_config_path: Path) -> dict[str, Any]:
    """Pull the non-trial blocks (scoring topics, task_board_limits, robot home)
    from the upstream sample_config.yaml so we stay in lockstep with the engine."""
    with open(sample_config_path) as f:
        sample = yaml.safe_load(f)
    return {
        "scoring": sample["scoring"],
        "task_board_limits": sample["task_board_limits"],
        "robot": sample["robot"],
    }


def render_session_config(
    trials: list[TrialConfig],
    out_path: Path,
    sample_config_path: Path,
) -> Path:
    """Emit a session YAML matching sample_config.yaml's shape, with N trials.

    Args:
      trials: list of TrialConfig (already randomized by randomizer.iter_trials).
      out_path: where to write the engine YAML.
      sample_config_path: path to aic_engine/config/sample_config.yaml (for global blocks).

    Returns: path to the written sidecar JSONL.
    """
    globals_ = _global_blocks_from_sample(sample_config_path)

    trial_blocks: "OrderedDict[str, Any]" = OrderedDict()
    for i, trial in enumerate(trials, start=1):
        key = f"trial_{i:06d}"
        trial_blocks[key] = _build_trial_block(trial)

    # Assemble in the canonical key order used by sample_config.yaml.
    doc: "OrderedDict[str, Any]" = OrderedDict()
    doc["scoring"] = globals_["scoring"]
    doc["task_board_limits"] = globals_["task_board_limits"]
    doc["trials"] = trial_blocks
    doc["robot"] = globals_["robot"]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        yaml.safe_dump(_to_plain(doc), f, sort_keys=False)

    sidecar = out_path.with_suffix(out_path.suffix + ".trials.jsonl")
    with open(sidecar, "w") as f:
        for i, trial in enumerate(trials, start=1):
            payload = {
                "trial_key": f"trial_{i:06d}",
                "trial_index_1based": i,
                "trial_config": trial.to_json_dict(),
            }
            f.write(json.dumps(payload, default=str) + "\n")

    return sidecar


def _to_plain(obj: Any) -> Any:
    """Convert OrderedDicts to plain dicts recursively so PyYAML emits in insertion order
    without the !!python/object tag."""
    if isinstance(obj, OrderedDict):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_plain(v) for v in obj]
    return obj
