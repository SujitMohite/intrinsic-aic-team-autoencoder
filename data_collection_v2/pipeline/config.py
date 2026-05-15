"""Sweep + per-trial config dataclasses.

Lifted verbatim from data_collection/pipeline/config.py.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml


PlugType = Literal["sfp", "sc"]


@dataclass
class SweepConfig:
    """Top-level sweep configuration loaded from YAML."""

    output_dir: str
    target_total_episodes: int
    seed_start: int = 1

    plug_distribution: dict[str, float] = field(
        default_factory=lambda: {"sfp": 0.60, "sc": 0.40}
    )
    nic_card_index_distribution: dict[str, list[int]] = field(
        default_factory=lambda: {"uniform_over": [0, 1, 2, 3, 4]}
    )
    sc_port_distribution: dict[str, list[int]] = field(
        default_factory=lambda: {"uniform_over": [0, 1]}
    )

    nic_rail_translation_range_m: tuple[float, float] = (-0.022, 0.022)
    nic_card_yaw_offset_range_rad: tuple[float, float] = (-0.17, 0.17)
    sc_rail_translation_range_m: tuple[float, float] = (-0.06, 0.055)

    task_board_x_range: tuple[float, float] = (0.25, 0.35)
    task_board_y_range: tuple[float, float] = (-0.15, -0.05)
    task_board_z_range: tuple[float, float] = (1.15, 1.25)
    task_board_yaw_range: tuple[float, float] = (0.0, 1.5708)

    grasp_offset_xyz_sigma_m: tuple[float, float, float] = (0.002, 0.002, 0.002)
    grasp_offset_rpy_sigma_rad: tuple[float, float, float] = (0.04, 0.04, 0.04)

    # Headless flags
    gazebo_gui: bool = False
    launch_rviz: bool = False
    disable_gi: bool = True
    camera_downsample_hw: tuple[int, int] = (256, 256)

    # Per-trial time limit written into the engine YAML.
    # CheatCode finishes in 15-25 s; 60 s caps pathological trials.
    per_trial_time_limit_s: int = 60

    # Quality gates
    quality_gate_every_n_episodes: int = 100
    min_success_rate: float = 0.85
    min_per_nic_demos: int = 40
    min_per_plug_demos: int = 250

    # Recorder
    image_jpg_quality: int = 85
    fps: int = 20  # /observations publish rate; written into LeRobot info.json

    # Policy — dotted module path; aic_model imports it and picks the class whose
    # name matches the last path component (aic_model.py:62-74). Upstream
    # baseline is "aic_example_policies.ros.CheatCode"; the v2 keystone runs use
    # the forked FastCheatCode which early-exits on /scoring/insertion_event.
    policy: str = "data_collection_v2.policy.FastCheatCode"

    # Container
    aic_eval_container_name: str = "aic_eval"

    @classmethod
    def from_yaml(cls, path: str | Path) -> SweepConfig:
        with open(path) as f:
            d = yaml.safe_load(f)
        for k in (
            "nic_rail_translation_range_m",
            "nic_card_yaw_offset_range_rad",
            "sc_rail_translation_range_m",
            "task_board_x_range",
            "task_board_y_range",
            "task_board_z_range",
            "task_board_yaw_range",
            "camera_downsample_hw",
        ):
            if k in d and isinstance(d[k], list):
                d[k] = tuple(d[k])
        for k in ("grasp_offset_xyz_sigma_m", "grasp_offset_rpy_sigma_rad"):
            if k in d and isinstance(d[k], list):
                d[k] = tuple(d[k])
        return cls(**d)


@dataclass
class TrialConfig:
    """One trial's randomized configuration."""

    ep_id: str
    seed: int
    plug_type: PlugType

    port_name: str
    target_module_name: str

    nic_card_index: int | None
    nic_rail: str | None
    nic_rail_translation_m: float | None
    nic_card_yaw_offset_rad: float | None

    sc_rail: str | None
    sc_rail_translation_m: float | None

    task_board_x: float
    task_board_y: float
    task_board_z: float
    task_board_yaw: float

    grasp_offset_x: float
    grasp_offset_y: float
    grasp_offset_z: float
    grasp_offset_roll: float
    grasp_offset_pitch: float
    grasp_offset_yaw: float

    cable_type: str = "sfp_sc_cable"
    time_limit_s: int = 60

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_metadata(self, path: str | Path) -> None:
        with open(path, "w") as f:
            json.dump(self.to_json_dict(), f, indent=2)
