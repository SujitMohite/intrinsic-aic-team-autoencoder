"""Stratified random sampler that produces TrialConfig instances from a SweepConfig.

Lifted verbatim from data_collection/pipeline/randomizer.py.
"""

from __future__ import annotations

import random
from typing import Iterator

from .config import PlugType, SweepConfig, TrialConfig


_PORT_NAMES_BY_PLUG = {
    "sfp": ["sfp_port_0", "sfp_port_1"],
    "sc": ["sc_port_0", "sc_port_1"],
}


def _ep_id(plug: str, nic_or_port: str, seed: int) -> str:
    return f"ep_gz_{plug}_{nic_or_port}_s{seed:06d}"


def _pick_plug(rng: random.Random, sweep: SweepConfig) -> PlugType:
    plugs = list(sweep.plug_distribution.keys())
    weights = list(sweep.plug_distribution.values())
    return rng.choices(plugs, weights=weights, k=1)[0]


def _pick_nic_index(rng: random.Random, sweep: SweepConfig) -> int:
    return rng.choice(sweep.nic_card_index_distribution["uniform_over"])


def _pick_sc_port_index(rng: random.Random, sweep: SweepConfig) -> int:
    return rng.choice(sweep.sc_port_distribution["uniform_over"])


def _uniform(rng: random.Random, lo_hi: tuple[float, float]) -> float:
    return rng.uniform(lo_hi[0], lo_hi[1])


def _gauss_bounded(
    rng: random.Random, sigma: float, n_sigma_cap: float = 3.0
) -> float:
    """Truncated Gaussian — won't deliver pathological samples."""
    v = rng.gauss(0.0, sigma)
    return max(-n_sigma_cap * sigma, min(n_sigma_cap * sigma, v))


def make_trial(seed: int, sweep: SweepConfig) -> TrialConfig:
    """Generate one TrialConfig deterministically from a seed."""
    rng = random.Random(seed)

    plug = _pick_plug(rng, sweep)
    task_board_x = _uniform(rng, sweep.task_board_x_range)
    task_board_y = _uniform(rng, sweep.task_board_y_range)
    task_board_z = _uniform(rng, sweep.task_board_z_range)
    task_board_yaw = _uniform(rng, sweep.task_board_yaw_range)

    trial = TrialConfig(
        ep_id="",
        seed=seed,
        plug_type=plug,
        port_name="",
        target_module_name="",
        nic_card_index=None,
        nic_rail=None,
        nic_rail_translation_m=None,
        nic_card_yaw_offset_rad=None,
        sc_rail=None,
        sc_rail_translation_m=None,
        task_board_x=task_board_x,
        task_board_y=task_board_y,
        task_board_z=task_board_z,
        task_board_yaw=task_board_yaw,
        grasp_offset_x=_gauss_bounded(rng, sweep.grasp_offset_xyz_sigma_m[0]),
        grasp_offset_y=_gauss_bounded(rng, sweep.grasp_offset_xyz_sigma_m[1]),
        grasp_offset_z=_gauss_bounded(rng, sweep.grasp_offset_xyz_sigma_m[2]),
        grasp_offset_roll=_gauss_bounded(rng, sweep.grasp_offset_rpy_sigma_rad[0]),
        grasp_offset_pitch=_gauss_bounded(rng, sweep.grasp_offset_rpy_sigma_rad[1]),
        grasp_offset_yaw=_gauss_bounded(rng, sweep.grasp_offset_rpy_sigma_rad[2]),
        time_limit_s=sweep.per_trial_time_limit_s,
    )

    if plug == "sfp":
        nic_idx = _pick_nic_index(rng, sweep)
        port_idx = rng.choice([0, 1])
        port_name = _PORT_NAMES_BY_PLUG["sfp"][port_idx]
        trial.nic_card_index = nic_idx
        trial.nic_rail = f"nic_rail_{nic_idx}"
        trial.nic_rail_translation_m = _uniform(rng, sweep.nic_rail_translation_range_m)
        trial.nic_card_yaw_offset_rad = _uniform(rng, sweep.nic_card_yaw_offset_range_rad)
        trial.target_module_name = f"nic_card_mount_{nic_idx}"
        trial.port_name = port_name
        trial.ep_id = _ep_id("sfp", f"nic{nic_idx}", seed)
    else:  # sc
        sc_idx = _pick_sc_port_index(rng, sweep)
        port_name = _PORT_NAMES_BY_PLUG["sc"][sc_idx]
        trial.sc_rail = f"sc_rail_{sc_idx}"
        trial.sc_rail_translation_m = _uniform(rng, sweep.sc_rail_translation_range_m)
        trial.target_module_name = f"sc_port_{sc_idx}"
        trial.port_name = port_name
        trial.ep_id = _ep_id("sc", f"port{sc_idx}", seed)

    return trial


def iter_trials(sweep: SweepConfig, skip_seeds: set[int] | None = None) -> Iterator[TrialConfig]:
    """Yield TrialConfig instances starting from sweep.seed_start.

    Stops after target_total_episodes have been yielded (not including skipped).
    skip_seeds: seeds already present in the manifest (restart resilience).
    """
    skip_seeds = skip_seeds or set()
    yielded = 0
    seed = sweep.seed_start
    while yielded < sweep.target_total_episodes:
        if seed in skip_seeds:
            seed += 1
            continue
        yield make_trial(seed, sweep)
        yielded += 1
        seed += 1
