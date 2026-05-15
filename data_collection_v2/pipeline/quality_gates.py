"""Quality gates: coverage + success-rate checks. Read manifest.jsonl, produce a report.

Lifted from data_collection/pipeline/quality_gates.py with minor tweaks for v2's
later-arriving scoring data (rows may have scoring=None until session-end finalization).
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

from .config import SweepConfig


_LOG = logging.getLogger("pipeline.quality_gates")


def _iter_manifest(manifest_path: Path):
    if not manifest_path.exists():
        return
    with open(manifest_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def compute_coverage(manifest_path: Path) -> dict[str, Any]:
    plug_count: Counter = Counter()
    nic_count: Counter = Counter()
    sc_count: Counter = Counter()
    tier3_scores: list[float] = []
    valid_count = 0
    scored_count = 0
    total = 0
    success_t3_50_plus = 0

    for row in _iter_manifest(manifest_path):
        total += 1
        tc = row.get("trial_config") or {}
        if row.get("valid"):
            valid_count += 1
        plug = tc.get("plug_type")
        if plug:
            plug_count[plug] += 1
        nic_idx = tc.get("nic_card_index")
        if isinstance(nic_idx, int):
            nic_count[nic_idx] += 1
        sc_rail = tc.get("sc_rail")
        if isinstance(sc_rail, str):
            sc_count[sc_rail] += 1
        scoring = row.get("scoring") or {}
        s = scoring.get("tier_3_score")
        if isinstance(s, (int, float)):
            tier3_scores.append(float(s))
            scored_count += 1
            if s > 50:
                success_t3_50_plus += 1

    return {
        "total_episodes": total,
        "valid_episodes": valid_count,
        "scored_episodes": scored_count,
        "plug_count": dict(plug_count),
        "nic_index_count": {str(k): v for k, v in nic_count.items()},
        "sc_rail_count": dict(sc_count),
        "tier3_mean": (sum(tier3_scores) / len(tier3_scores)) if tier3_scores else 0.0,
        "tier3_above_50_rate": (success_t3_50_plus / scored_count) if scored_count else 0.0,
        "valid_rate": (valid_count / total) if total else 0.0,
    }


def check_gates(coverage: dict[str, Any], sweep: SweepConfig) -> list[str]:
    warnings: list[str] = []

    total = coverage["total_episodes"]
    valid_rate = coverage["valid_rate"]
    if total >= sweep.quality_gate_every_n_episodes and valid_rate < sweep.min_success_rate:
        warnings.append(
            f"valid_rate {valid_rate:.2%} below min {sweep.min_success_rate:.0%} "
            f"(over {total} episodes)"
        )

    for plug, want in (
        ("sfp", sweep.min_per_plug_demos // 2),
        ("sc", sweep.min_per_plug_demos // 2),
    ):
        if total >= 200:
            got = coverage["plug_count"].get(plug, 0)
            if got < want:
                warnings.append(f"plug={plug} coverage {got} < min {want}")

    if total >= 500:
        for nic_idx in range(5):
            got = coverage["nic_index_count"].get(str(nic_idx), 0)
            if got < sweep.min_per_nic_demos:
                warnings.append(f"NIC {nic_idx} coverage {got} < min {sweep.min_per_nic_demos}")

    return warnings


def write_report(manifest_path: Path, report_path: Path, sweep: SweepConfig) -> dict[str, Any]:
    coverage = compute_coverage(manifest_path)
    warnings = check_gates(coverage, sweep)
    report = {
        "coverage": coverage,
        "warnings": warnings,
        "gates_passed": not warnings,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    _LOG.info(
        "quality gate: total=%d valid=%d t3_mean=%.1f warnings=%d",
        coverage["total_episodes"],
        coverage["valid_episodes"],
        coverage["tier3_mean"],
        len(warnings),
    )
    for w in warnings:
        _LOG.warning("  - %s", w)
    return report
