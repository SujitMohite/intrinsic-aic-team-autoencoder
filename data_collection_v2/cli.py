"""CLI entry point for the v2 data-collection pipeline.

Commands:
  smoke     run a 10-trial validation session (configs/smoke.yaml)
  session   run a full session against a user-provided config
  resume    continue an existing run (reads manifest, skips completed seeds)
  report    no-collection: compute coverage report + finalize dataset meta files

Usage:
  pixi run python -m data_collection_v2.cli smoke
  pixi run python -m data_collection_v2.cli session \
      --config data_collection_v2/configs/keystone_1500.yaml \
      --output /data/aic_v2/run_$(date +%Y%m%d_%H%M)
  pixi run python -m data_collection_v2.cli resume --output /data/aic_v2/run_20260514_1200
  pixi run python -m data_collection_v2.cli report --output /data/aic_v2/run_20260514_1200
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from data_collection_v2.session_driver import (
    REPO_ROOT,
    report_only,
    run_coverage,
    run_session,
    run_yaw_sweep,
)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
        datefmt="%H:%M:%S",
    )


def _cmd_smoke(args: argparse.Namespace) -> int:
    config = REPO_ROOT / "data_collection_v2" / "configs" / "smoke.yaml"
    output = Path(args.output or "/tmp/aic_v2_smoke")
    return run_session(config, output)


def _cmd_coverage(args: argparse.Namespace) -> int:
    config = REPO_ROOT / "data_collection_v2" / "configs" / "coverage.yaml"
    output = Path(args.output or "/tmp/aic_v2_coverage")
    return run_coverage(config, output)


def _cmd_yaw_sweep(args: argparse.Namespace) -> int:
    config = REPO_ROOT / "data_collection_v2" / "configs" / "coverage.yaml"
    output = Path(args.output or "/tmp/aic_v2_yaw_sweep")
    return run_yaw_sweep(config, output)


def _cmd_session(args: argparse.Namespace) -> int:
    config = Path(args.config).resolve()
    output = Path(args.output).resolve()
    return run_session(config, output)


def _cmd_resume(args: argparse.Namespace) -> int:
    output = Path(args.output).resolve()
    # Resume reads the most recent session yaml to find the sweep config; if
    # the user passed --config we use that explicitly.
    if args.config:
        config = Path(args.config).resolve()
    else:
        sessions = sorted((output / "sessions").glob("session_*.yaml"))
        if not sessions:
            print(f"ERROR: no prior sessions under {output}/sessions/; pass --config explicitly", file=sys.stderr)
            return 2
        # Fall back to whatever config produced the most recent session — but
        # we don't actually store the source config alongside the session yaml,
        # so the safer bet is to require --config on resume. Surface that.
        print(
            "ERROR: --config is required for resume "
            "(v2 doesn't yet persist the source sweep YAML next to sessions/)",
            file=sys.stderr,
        )
        return 2
    return run_session(config, output)


def _cmd_report(args: argparse.Namespace) -> int:
    return report_only(Path(args.output).resolve())


def main(argv: list[str] | None = None) -> int:
    _setup_logging()
    parser = argparse.ArgumentParser(prog="data_collection_v2")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_smoke = sub.add_parser("smoke", help="run the 10-trial smoke session")
    p_smoke.add_argument("--output", default=None, help="output dir (default /tmp/aic_v2_smoke)")
    p_smoke.set_defaults(func=_cmd_smoke)

    p_cov = sub.add_parser(
        "coverage",
        help="run the 12-trial plug × target × port coverage test",
    )
    p_cov.add_argument(
        "--output", default=None, help="output dir (default /tmp/aic_v2_coverage)"
    )
    p_cov.set_defaults(func=_cmd_coverage)

    p_yaw = sub.add_parser(
        "yaw_sweep",
        help="5-trial board-yaw sweep (diagnostic, ~7 min)",
    )
    p_yaw.add_argument(
        "--output", default=None, help="output dir (default /tmp/aic_v2_yaw_sweep)"
    )
    p_yaw.set_defaults(func=_cmd_yaw_sweep)

    p_sess = sub.add_parser("session", help="run a full collection session")
    p_sess.add_argument("--config", required=True, help="path to sweep YAML")
    p_sess.add_argument("--output", required=True, help="output dir for this run")
    p_sess.set_defaults(func=_cmd_session)

    p_res = sub.add_parser("resume", help="resume a previous run")
    p_res.add_argument("--config", required=True, help="path to sweep YAML used originally")
    p_res.add_argument("--output", required=True, help="output dir of the prior run")
    p_res.set_defaults(func=_cmd_resume)

    p_rep = sub.add_parser("report", help="compute coverage + finalize dataset (no collection)")
    p_rep.add_argument("--output", required=True, help="output dir of the run")
    p_rep.set_defaults(func=_cmd_report)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
