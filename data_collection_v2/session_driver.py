"""Host-side session driver.

What it does (NOT what a trial does — see container/v2_entrypoint.sh for that):

  1. Load SweepConfig + (optional) prior manifest.
  2. Generate N TrialConfigs using randomizer.iter_trials.
  3. Render session_<id>.yaml + sidecar JSONL via session_yaml.render_session_config.
  4. (Optional) apply_gi_off.sh on the world SDF.
  5. distrobox-exec v2_entrypoint.sh inside aic_eval; stream container logs to disk.
  6. Tail the manifest.jsonl for progress; emit periodic quality-gate reports.
  7. After the container exits, parse the engine's session-end scoring.yaml,
     backfill manifest rows with per-trial scoring, and finalize the LeRobot v2
     dataset (info.json + stats.json).

This script does NOT spawn distrobox per-trial. The container starts ONCE per
session and the engine handles all per-trial resets internally (aic_engine.cpp:583).
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml

from data_collection_v2.pipeline.config import SweepConfig, TrialConfig
from data_collection_v2.pipeline.lerobot_v2_writer import WriteSession
from data_collection_v2.pipeline.manifest import Manifest
from data_collection_v2.pipeline.quality_gates import write_report
from data_collection_v2.pipeline.randomizer import iter_trials
from data_collection_v2.pipeline.session_yaml import render_session_config


_LOG = logging.getLogger("session_driver")

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CONFIG = REPO_ROOT / "aic_engine" / "config" / "sample_config.yaml"


@dataclass
class SessionPaths:
    output_dir: Path
    session_yaml: Path
    sidecar_jsonl: Path
    manifest_path: Path
    coverage_report: Path
    container_logs: Path
    aic_results_dir: Path

    @classmethod
    def make(cls, output_dir: Path, session_id: str) -> "SessionPaths":
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        sessions = output_dir / "sessions"
        sessions.mkdir(parents=True, exist_ok=True)
        session_yaml = sessions / f"session_{session_id}.yaml"
        return cls(
            output_dir=output_dir,
            session_yaml=session_yaml,
            sidecar_jsonl=session_yaml.with_suffix(session_yaml.suffix + ".trials.jsonl"),
            manifest_path=output_dir / "manifest.jsonl",
            coverage_report=output_dir / "coverage_report.json",
            container_logs=output_dir / "logs",
            aic_results_dir=output_dir / "engine_results",
        )


def _session_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _docker_container_running(container: str) -> bool:
    """True iff `docker container inspect` reports the container as Running."""
    try:
        r = subprocess.run(
            ["docker", "container", "inspect", container, "-f", "{{.State.Running}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0 and r.stdout.strip() == "true"


def _distrobox_has(container: str) -> bool:
    """True iff distrobox knows about the container (user or root mode)."""
    for args in (["distrobox", "list"], ["distrobox", "list", "--root"]):
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=10)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
        if r.returncode == 0 and container in r.stdout:
            return True
    return False


def _preflight(sweep: SweepConfig, paths: SessionPaths) -> None:
    """Cheap sanity checks before we burn an hour on a broken setup."""
    stats = shutil.disk_usage(paths.output_dir)
    if stats.free < 50 * 1024**3:
        _LOG.warning(
            "disk free %.1f GB < recommended 50 GB at %s",
            stats.free / 1024**3,
            paths.output_dir,
        )

    container = sweep.aic_eval_container_name
    runtime_hint = os.environ.get("AIC_V2_CONTAINER_RUNTIME", "").lower()
    if runtime_hint in ("docker", "distrobox"):
        _LOG.info("container runtime forced to %r via AIC_V2_CONTAINER_RUNTIME", runtime_hint)
    elif _docker_container_running(container):
        _LOG.info("container runtime: docker exec (auto-detected running %r)", container)
    elif _distrobox_has(container):
        _LOG.info("container runtime: distrobox enter (%r registered)", container)
    else:
        _LOG.warning(
            "container %r not found via docker or distrobox. "
            "Create or start it per docs/getting_started.md.",
            container,
        )

    if not SAMPLE_CONFIG.exists():
        raise RuntimeError(f"sample_config.yaml not found at {SAMPLE_CONFIG}")


TrialsProvider = Callable[[SweepConfig, set[int]], list[TrialConfig]]


def _generate_trials(
    sweep: SweepConfig,
    manifest: Manifest,
    trials_provider: TrialsProvider | None = None,
) -> list[TrialConfig]:
    """Skip seeds already in the manifest. Returns the trial list to collect.

    If `trials_provider` is supplied (e.g. the coverage enumerator), it is
    called instead of the stratified randomizer. Caller is responsible for any
    target-count semantics.
    """
    skip = manifest.read_completed_seeds()
    if skip:
        _LOG.info("resuming: skipping %d already-collected seeds", len(skip))
    if trials_provider is not None:
        trials = trials_provider(sweep, skip)
    else:
        trials = list(iter_trials(sweep, skip_seeds=skip))
    _LOG.info("generated %d trials (target %d)", len(trials), sweep.target_total_episodes)
    return trials


def _maybe_apply_gi_off(sweep: SweepConfig) -> None:
    if not sweep.disable_gi:
        return
    script = REPO_ROOT / "data_collection_v2" / "scripts" / "apply_gi_off.sh"
    if not script.exists():
        _LOG.warning("apply_gi_off.sh not found at %s", script)
        return
    try:
        subprocess.run(["bash", str(script)], check=True, timeout=30)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        _LOG.warning("apply_gi_off failed (continuing without GI tweak): %s", e)


def _build_container_cmd(
    container: str,
    entrypoint_script: Path,
    env: dict[str, str],
) -> tuple[list[str], str]:
    """Pick `docker exec` if the container is a running docker container,
    else `distrobox enter`. Override the choice with env AIC_V2_CONTAINER_RUNTIME
    set to "docker" or "distrobox".

    Returns (argv, runtime_label).
    """
    forced = os.environ.get("AIC_V2_CONTAINER_RUNTIME", "").lower()
    if forced == "docker":
        use_docker = True
    elif forced == "distrobox":
        use_docker = False
    else:
        use_docker = _docker_container_running(container)

    if use_docker:
        cmd = ["docker", "exec"]
        for k, v in env.items():
            cmd += ["-e", f"{k}={v}"]
        cmd += [container, "bash", str(entrypoint_script)]
        return cmd, "docker"

    # distrobox fallback (only if user explicitly created the container via distrobox).
    use_root = os.environ.get("AIC_DISTROBOX_ROOT", "0") == "1"
    env_prefix = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
    inner = f"{env_prefix} bash {shlex.quote(str(entrypoint_script))}"
    cmd = ["distrobox", "enter"]
    if use_root:
        cmd.append("-r")
    cmd += [container, "--", "bash", "-lc", inner]
    return cmd, "distrobox"


def _spawn_container(
    sweep: SweepConfig,
    paths: SessionPaths,
    log_path: Path,
) -> subprocess.Popen:
    entrypoint = REPO_ROOT / "data_collection_v2" / "container" / "v2_entrypoint.sh"
    if not entrypoint.exists():
        raise FileNotFoundError(entrypoint)
    env = {
        "AIC_V2_SESSION_YAML": str(paths.session_yaml),
        "AIC_V2_TRIAL_CONFIGS": str(paths.sidecar_jsonl),
        "AIC_V2_OUTPUT_DIR": str(paths.output_dir),
        "AIC_V2_LOG_DIR": str(paths.container_logs),
        "AIC_V2_REPO_ROOT": str(REPO_ROOT),
        "AIC_RESULTS_DIR": str(paths.aic_results_dir),
        "AIC_V2_FPS": str(sweep.fps),
        "AIC_V2_JPG_QUALITY": str(sweep.image_jpg_quality),
        "AIC_V2_CAMERA_H": str(sweep.camera_downsample_hw[0]),
        "AIC_V2_CAMERA_W": str(sweep.camera_downsample_hw[1]),
        "AIC_V2_GAZEBO_GUI": "true" if sweep.gazebo_gui else "false",
        "AIC_V2_LAUNCH_RVIZ": "true" if sweep.launch_rviz else "false",
        "AIC_V2_POLICY": sweep.policy,
    }
    paths.aic_results_dir.mkdir(parents=True, exist_ok=True)
    paths.container_logs.mkdir(parents=True, exist_ok=True)

    cmd, runtime = _build_container_cmd(
        sweep.aic_eval_container_name, entrypoint, env
    )
    _LOG.info("spawning container (%s): %s", runtime, " ".join(cmd))
    log_f = open(log_path, "wb")
    proc = subprocess.Popen(
        cmd,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        cwd=str(REPO_ROOT),
        preexec_fn=os.setsid,
    )
    return proc


def _wait_with_progress(
    proc: subprocess.Popen,
    sweep: SweepConfig,
    paths: SessionPaths,
    expected_trials: int,
) -> int:
    """Poll the manifest for progress while the container runs.

    Returns: the container subprocess's exit code.
    """
    manifest = Manifest(paths.manifest_path)
    start = time.time()
    last_count = -1
    next_gate = sweep.quality_gate_every_n_episodes
    while proc.poll() is None:
        now_count = manifest.count()
        if now_count != last_count:
            elapsed = time.time() - start
            rate = (now_count / elapsed) * 3600 if elapsed > 0 else 0.0
            _LOG.info(
                "[%5.1fm] progress %d/%d (%.0f ep/h)",
                elapsed / 60,
                now_count,
                expected_trials,
                rate,
            )
            last_count = now_count
            if now_count >= next_gate:
                write_report(paths.manifest_path, paths.coverage_report, sweep)
                next_gate += sweep.quality_gate_every_n_episodes
        time.sleep(5.0)
    return proc.returncode


def _backfill_scoring(paths: SessionPaths) -> None:
    """Read the engine's session-end scoring.yaml and merge per-trial scores into
    the manifest rows.

    Engine schema (aic_engine.cpp Score::serialize ~line 266-276):
      total: <float>
      trial_<key>: { tier_1: {...}, tier_2: {...}, tier_3: {...}, total: <float> }
    where <key> is the trial map key from the input config — for v2 these are
    'trial_000001' .. 'trial_NNNNNN'.
    """
    scoring_path = paths.aic_results_dir / "scoring.yaml"
    if not scoring_path.exists():
        _LOG.warning("no scoring.yaml at %s — manifest scoring will remain null", scoring_path)
        return
    with open(scoring_path) as f:
        raw = yaml.safe_load(f) or {}
    # Build a map: trial_key -> per-trial dict.
    per_trial: dict[str, dict[str, Any]] = {}
    for k, v in raw.items():
        if isinstance(k, str) and k.startswith("trial_") and isinstance(v, dict):
            per_trial[k] = v

    if not per_trial:
        _LOG.warning("scoring.yaml has no per-trial blocks — schema unexpected")
        return

    manifest = Manifest(paths.manifest_path)
    rows = manifest.read_all()
    n_updated = 0
    for row in rows:
        tk = row.get("trial_key")
        if not tk or tk not in per_trial:
            continue
        t = per_trial[tk]
        tier1 = (t.get("tier_1") or {})
        tier2 = (t.get("tier_2") or {})
        tier3 = (t.get("tier_3") or {})
        # tier_1 schema (from sample scoring.yaml):
        #   tier_1: {score: 0|1, message: "..."}
        # score == 1 means the model passed validation.
        tier_1_score = int(tier1.get("score") or 0)
        tier_2_score = float(tier2.get("score") or 0.0)
        tier_3_score = float(tier3.get("score") or 0.0)
        # Per-trial scoring.yaml schema has no `total` field — only the session-wide
        # `total` at the root. Sum the tier scores ourselves so each manifest row
        # carries a meaningful trial total.
        per_trial_total = float(tier_1_score) + tier_2_score + tier_3_score
        summary = {
            "tier_1_score": tier_1_score,
            "tier_1_message": str(tier1.get("message") or ""),
            "tier_2_score": tier_2_score,
            "tier_3_score": tier_3_score,
            "tier_3_message": str(tier3.get("message") or ""),
            "total": per_trial_total,
        }
        row["scoring"] = summary
        row["valid"] = tier_1_score == 1
        n_updated += 1
    if n_updated:
        manifest.rewrite(rows)
        _LOG.info("backfilled scoring into %d manifest rows", n_updated)


def _finalize_dataset(paths: SessionPaths, sweep: SweepConfig) -> None:
    """Write meta/info.json + meta/stats.json for the LeRobot v2 dataset.

    The recorder appended episodes.jsonl + tasks.jsonl as it went, but info.json
    + stats.json need the totals which are only known once the session is done.

    v2_entrypoint.sh already runs this from inside the container after the engine
    exits, so by the time the host gets here the files usually exist. We try
    anyway as a host-side safety net, and tolerate PermissionError because the
    container wrote those files as root — the in-container finalize is the
    authoritative one.
    """
    ws = WriteSession(
        root=paths.output_dir / "lerobot_v2",
        fps=sweep.fps,
        camera_hw=tuple(sweep.camera_downsample_hw),
    )
    try:
        ws.finalize()
    except PermissionError as e:
        info_path = paths.output_dir / "lerobot_v2" / "meta" / "info.json"
        if info_path.exists():
            _LOG.info(
                "host-side finalize skipped (container already wrote %s): %s",
                info_path.name,
                e,
            )
        else:
            _LOG.error(
                "host-side finalize failed AND no info.json on disk: %s. "
                "Re-run from inside container as root: "
                "`docker exec %s python3 -c \"from data_collection_v2.pipeline.lerobot_v2_writer "
                "import WriteSession; WriteSession(root='%s/lerobot_v2', fps=%d, "
                "camera_hw=%s).finalize()\"`",
                e,
                sweep.aic_eval_container_name,
                paths.output_dir,
                sweep.fps,
                tuple(sweep.camera_downsample_hw),
            )


# ---- Top-level entry ----


def run_session(
    config_path: Path,
    output_dir: Path,
    trials_provider: TrialsProvider | None = None,
) -> int:
    sweep = SweepConfig.from_yaml(config_path)
    session_id = _session_id()
    paths = SessionPaths.make(output_dir, session_id)
    _LOG.info("session id: %s", session_id)
    _LOG.info("output dir: %s", paths.output_dir)

    _preflight(sweep, paths)
    _maybe_apply_gi_off(sweep)

    manifest = Manifest(paths.manifest_path)
    trials = _generate_trials(sweep, manifest, trials_provider=trials_provider)
    if not trials:
        _LOG.info("nothing to collect (manifest already has all target seeds)")
        _finalize_dataset(paths, sweep)
        return 0

    render_session_config(
        trials=trials,
        out_path=paths.session_yaml,
        sample_config_path=SAMPLE_CONFIG,
    )
    _LOG.info(
        "wrote session yaml (%d trials) -> %s",
        len(trials),
        paths.session_yaml,
    )

    log_path = paths.container_logs / f"session_{session_id}.log"
    proc = _spawn_container(sweep, paths, log_path)

    # Forward TERM/INT to the container.
    def _signal_handler(signum, frame):  # noqa: ARG001
        _LOG.warning("received signal %d; sending SIGTERM to container", signum)
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    rc = _wait_with_progress(proc, sweep, paths, expected_trials=len(trials))
    _LOG.info("container exited with rc=%d", rc)

    # Backfill scoring + finalize dataset whether or not the engine completed
    # cleanly — partial data is still useful.
    _backfill_scoring(paths)
    _finalize_dataset(paths, sweep)
    write_report(paths.manifest_path, paths.coverage_report, sweep)
    return rc


def report_only(output_dir: Path) -> int:
    """No-collection mode: read manifest + scoring.yaml, write coverage report
    and re-finalize the dataset meta files."""
    output_dir = Path(output_dir).resolve()
    paths = SessionPaths.make(output_dir, session_id="report")
    # Look for any existing engine_results/scoring.yaml.
    if paths.aic_results_dir.exists():
        _backfill_scoring(paths)

    # Pick the most recent session yaml for sweep defaults — fall back to a bare
    # SweepConfig if none found.
    sessions = sorted((paths.output_dir / "sessions").glob("session_*.yaml")) if (paths.output_dir / "sessions").exists() else []
    if sessions:
        # Use a minimal sweep — we just need fps + camera_hw for finalize().
        sweep = SweepConfig(
            output_dir=str(paths.output_dir),
            target_total_episodes=0,
        )
    else:
        sweep = SweepConfig(
            output_dir=str(paths.output_dir),
            target_total_episodes=0,
        )
    _finalize_dataset(paths, sweep)
    write_report(paths.manifest_path, paths.coverage_report, sweep)
    print(json.dumps(json.loads(paths.coverage_report.read_text()), indent=2))
    return 0


def run_coverage(config_path: Path, output_dir: Path) -> int:
    """Run the 12-trial plug×target×port coverage test.

    Returns 0 only if every expected combo has a manifest row with valid=true
    AND tier_1_score == 1. A non-zero return signals a structural failure that
    must be investigated before the keystone run.
    """
    from data_collection_v2.pipeline.coverage import (
        enumerate_coverage_trials,
        expected_combos,
    )

    rc = run_session(
        config_path,
        output_dir,
        trials_provider=enumerate_coverage_trials,
    )

    manifest_path = Path(output_dir).resolve() / "manifest.jsonl"
    if not manifest_path.exists():
        _LOG.error("no manifest at %s — coverage check skipped", manifest_path)
        return rc or 2

    seen: dict[tuple[str, str, str], dict[str, Any]] = {}
    with manifest_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            tc = row.get("trial_config", {})
            key = (
                tc.get("plug_type"),
                tc.get("target_module_name"),
                tc.get("port_name"),
            )
            seen[key] = row

    expected = expected_combos()
    succeeded: list[tuple[str, str, str]] = []
    failed: list[tuple[str, str, str]] = []
    missing: list[tuple[str, str, str]] = []
    for combo in expected:
        row = seen.get(combo)
        if row is None:
            missing.append(combo)
            continue
        tier_1 = (row.get("scoring") or {}).get("tier_1_score")
        if bool(row.get("valid")) and tier_1 == 1:
            succeeded.append(combo)
        else:
            failed.append(combo)

    _print_coverage_table(expected, set(succeeded), set(failed), set(missing), seen)
    _LOG.info(
        "coverage: %d/%d combos OK (%d failed, %d missing)",
        len(succeeded),
        len(expected),
        len(failed),
        len(missing),
    )

    if missing or failed:
        return rc or 1
    return rc


def run_yaw_sweep(config_path: Path, output_dir: Path) -> int:
    """5-trial board-yaw sweep at a known-good combo. Diagnostic only.

    Returns 0 if every trial has valid=true AND tier_3_score >= 60 (top-30
    floor); returns 1 if FastCheatCode breaks down at any yaw. Either way the
    per-trial table is printed so we can see the dropoff curve.
    """
    from data_collection_v2.pipeline.coverage import enumerate_yaw_sweep_trials

    rc = run_session(
        config_path,
        output_dir,
        trials_provider=enumerate_yaw_sweep_trials,
    )

    manifest_path = Path(output_dir).resolve() / "manifest.jsonl"
    if not manifest_path.exists():
        _LOG.error("no manifest at %s — yaw_sweep check skipped", manifest_path)
        return rc or 2

    rows: list[dict[str, Any]] = []
    with manifest_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    rows.sort(key=lambda r: r.get("trial_config", {}).get("task_board_yaw", 0))

    print()
    print("Yaw sweep (SFP × nic_card_mount_1 × sfp_port_0):")
    print(f"{'#':>2}  {'yaw_rad':<9}  {'yaw_deg':<8}  {'valid':<5}  {'t1':<3}  {'t2':<7}  {'t3':<7}  total")
    print("-" * 64)
    all_ok = True
    for i, row in enumerate(rows, 1):
        yaw = row.get("trial_config", {}).get("task_board_yaw", 0.0)
        valid = bool(row.get("valid"))
        scoring = row.get("scoring") or {}
        t1 = scoring.get("tier_1_score")
        t2 = scoring.get("tier_2_score")
        t3 = scoring.get("tier_3_score")
        total = scoring.get("total")
        fmt = lambda v: f"{v:7.2f}" if isinstance(v, (int, float)) else "    -  "
        print(
            f"{i:>2}  {yaw:<9.3f}  {(yaw * 180.0 / 3.14159265):<8.1f}  "
            f"{str(valid):<5}  {str(t1):<3}  {fmt(t2)}  {fmt(t3)}  {fmt(total)}"
        )
        if not (valid and isinstance(t3, (int, float)) and t3 >= 60):
            all_ok = False
    print()

    if all_ok:
        _LOG.info("yaw_sweep: PASS — FastCheatCode handles ±0.5 rad yaw envelope")
        return rc
    _LOG.warning("yaw_sweep: FAIL — at least one yaw produced t3 < 60 or invalid")
    return rc or 1


def _print_coverage_table(
    expected: list[tuple[str, str, str]],
    ok: set[tuple[str, str, str]],
    fail: set[tuple[str, str, str]],
    miss: set[tuple[str, str, str]],
    seen: dict[tuple[str, str, str], dict[str, Any]],
) -> None:
    print()
    print("Coverage results:")
    print(f"{'#':>2}  {'plug':<4}  {'target_module':<18}  {'port':<14}  {'status':<6}  total_score")
    print("-" * 72)
    for i, combo in enumerate(expected, 1):
        plug, target, port = combo
        if combo in ok:
            status = "OK"
        elif combo in fail:
            status = "FAIL"
        else:
            status = "MISS"
        total = (seen.get(combo, {}).get("scoring") or {}).get("total")
        score_str = f"{total:.2f}" if isinstance(total, (int, float)) else ""
        print(f"{i:>2}  {plug:<4}  {target:<18}  {port:<14}  {status:<6}  {score_str}")
    print()
