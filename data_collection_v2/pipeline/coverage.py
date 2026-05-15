"""Deterministic 12-trial enumeration: one trial per (plug, target, port) combo.

Used by the `coverage` CLI subcommand to verify the pipeline can collect data
for every plug-type / port combination the AIC task board supports. Unlike
`randomizer.iter_trials`, this enumerator does NOT sample — it produces an
exhaustive, fully-determined list, with all randomization axes zeroed and the
task board at the canonical pose from aic_engine/config/sample_config.yaml.

Combos (12 total):
  - SFP × {nic_card_mount_0..4} × {sfp_port_0, sfp_port_1}  (10)
  - SC  × {sc_port_0, sc_port_1} × sc_port_base             (2)
"""

from __future__ import annotations

from .config import SweepConfig, TrialConfig

# Anchor seed for coverage; disjoint from smoke (1..3) and keystone (1..1500)
# so a single output dir can hold all three categories without seed collisions.
_COVERAGE_SEED_BASE = 1001

# Canonical task-board pose from aic_engine/config/sample_config.yaml:67-72.
_DEFAULT_BOARD_X = 0.15
_DEFAULT_BOARD_Y = -0.20
_DEFAULT_BOARD_Z = 1.14
_DEFAULT_BOARD_YAW = 3.1415

_NIC_INDICES = (0, 1, 2, 3, 4)
_SFP_PORT_INDICES = (0, 1)
_SC_PORT_INDICES = (0, 1)


def _make_sfp_trial(seed: int, nic_idx: int, port_idx: int, time_limit_s: int) -> TrialConfig:
    return TrialConfig(
        ep_id=f"ep_cov_sfp_nic{nic_idx}_p{port_idx}",
        seed=seed,
        plug_type="sfp",
        port_name=f"sfp_port_{port_idx}",
        target_module_name=f"nic_card_mount_{nic_idx}",
        nic_card_index=nic_idx,
        nic_rail=f"nic_rail_{nic_idx}",
        nic_rail_translation_m=0.0,
        nic_card_yaw_offset_rad=0.0,
        sc_rail=None,
        sc_rail_translation_m=None,
        task_board_x=_DEFAULT_BOARD_X,
        task_board_y=_DEFAULT_BOARD_Y,
        task_board_z=_DEFAULT_BOARD_Z,
        task_board_yaw=_DEFAULT_BOARD_YAW,
        grasp_offset_x=0.0,
        grasp_offset_y=0.0,
        grasp_offset_z=0.0,
        grasp_offset_roll=0.0,
        grasp_offset_pitch=0.0,
        grasp_offset_yaw=0.0,
        time_limit_s=time_limit_s,
    )


def _make_sc_trial(seed: int, sc_idx: int, time_limit_s: int) -> TrialConfig:
    return TrialConfig(
        ep_id=f"ep_cov_sc_p{sc_idx}",
        seed=seed,
        plug_type="sc",
        port_name="sc_port_base",
        target_module_name=f"sc_port_{sc_idx}",
        nic_card_index=None,
        nic_rail=None,
        nic_rail_translation_m=None,
        nic_card_yaw_offset_rad=None,
        sc_rail=f"sc_rail_{sc_idx}",
        sc_rail_translation_m=0.0,
        task_board_x=_DEFAULT_BOARD_X,
        task_board_y=_DEFAULT_BOARD_Y,
        task_board_z=_DEFAULT_BOARD_Z,
        task_board_yaw=_DEFAULT_BOARD_YAW,
        grasp_offset_x=0.0,
        grasp_offset_y=0.0,
        grasp_offset_z=0.0,
        grasp_offset_roll=0.0,
        grasp_offset_pitch=0.0,
        grasp_offset_yaw=0.0,
        time_limit_s=time_limit_s,
    )


def expected_combos() -> list[tuple[str, str, str]]:
    """The 12 (plug_type, target_module_name, port_name) tuples we expect to see
    in the manifest after a full coverage run. Pure — no SweepConfig needed."""
    combos: list[tuple[str, str, str]] = []
    for n in _NIC_INDICES:
        for p in _SFP_PORT_INDICES:
            combos.append(("sfp", f"nic_card_mount_{n}", f"sfp_port_{p}"))
    for s in _SC_PORT_INDICES:
        combos.append(("sc", f"sc_port_{s}", "sc_port_base"))
    return combos


def enumerate_yaw_sweep_trials(
    sweep: SweepConfig, skip_seeds: set[int] | None = None
) -> list[TrialConfig]:
    """5-trial board-yaw sweep at a known-good combo.

    Holds (plug=SFP, target=nic_card_mount_1, port=sfp_port_0) constant; varies
    only `task_board_yaw` over [π-0.5, π-0.25, π, π+0.25, π+0.5] rad. Used to
    answer "does FastCheatCode still produce leaderboard-quality demos at wider
    yaw than the smoke envelope?" before redesigning keystone DR ranges.

    Seeds 1101..1105, disjoint from coverage (1001..1012) and keystone (1..1500).
    """
    import math

    skip = skip_seeds or set()
    yaws = [math.pi - 0.5, math.pi - 0.25, math.pi, math.pi + 0.25, math.pi + 0.5]
    trials: list[TrialConfig] = []
    time_limit_s = sweep.per_trial_time_limit_s

    for i, yaw in enumerate(yaws):
        seed = 1101 + i
        if seed in skip:
            continue
        trials.append(
            TrialConfig(
                ep_id=f"ep_yawsweep_y{yaw:.3f}",
                seed=seed,
                plug_type="sfp",
                port_name="sfp_port_0",
                target_module_name="nic_card_mount_1",
                nic_card_index=1,
                nic_rail="nic_rail_1",
                nic_rail_translation_m=0.0,
                nic_card_yaw_offset_rad=0.0,
                sc_rail=None,
                sc_rail_translation_m=None,
                task_board_x=_DEFAULT_BOARD_X,
                task_board_y=_DEFAULT_BOARD_Y,
                task_board_z=_DEFAULT_BOARD_Z,
                task_board_yaw=yaw,
                grasp_offset_x=0.0,
                grasp_offset_y=0.0,
                grasp_offset_z=0.0,
                grasp_offset_roll=0.0,
                grasp_offset_pitch=0.0,
                grasp_offset_yaw=0.0,
                time_limit_s=time_limit_s,
            )
        )
    return trials


def enumerate_coverage_trials(
    sweep: SweepConfig, skip_seeds: set[int] | None = None
) -> list[TrialConfig]:
    """Return the 12 coverage TrialConfigs, minus any whose seed is in skip_seeds.

    Seeds run from _COVERAGE_SEED_BASE (1001) upward, in this order:
      1001..1010 — SFP × nic{0..4} × port{0,1} (row-major: nic outer, port inner)
      1011..1012 — SC × port{0,1}
    """
    skip = skip_seeds or set()
    trials: list[TrialConfig] = []
    seed = _COVERAGE_SEED_BASE
    time_limit_s = sweep.per_trial_time_limit_s

    for nic_idx in _NIC_INDICES:
        for port_idx in _SFP_PORT_INDICES:
            if seed not in skip:
                trials.append(_make_sfp_trial(seed, nic_idx, port_idx, time_limit_s))
            seed += 1

    for sc_idx in _SC_PORT_INDICES:
        if seed not in skip:
            trials.append(_make_sc_trial(seed, sc_idx, time_limit_s))
        seed += 1

    return trials
