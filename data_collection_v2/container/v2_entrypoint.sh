#!/usr/bin/env bash
# v2 entrypoint — runs INSIDE the aic_eval distrobox container.
#
# Starts (in this order, with cleanup on EXIT):
#   1. rmw_zenohd               (background)
#   2. aic_model + CheatCode    (background)
#   3. data_collection_v2_recorder (background)
#   4. aic_bringup launch with start_aic_engine:=true (foreground; blocks)
#
# The engine loops through every trial in the session YAML (aic_engine.cpp:583-615),
# resetting between trials via reset_after_trial. When the engine exits cleanly,
# shutdown_on_aic_engine_exit:=true tears the launch tree down.
#
# Required env vars:
#   AIC_V2_SESSION_YAML    /path/to/session_<id>.yaml          (engine config)
#   AIC_V2_TRIAL_CONFIGS   /path/to/session_<id>.yaml.trials.jsonl
#   AIC_V2_OUTPUT_DIR      /path/to/dataset root (e.g. /data/aic_v2/run_xxx)
#   AIC_RESULTS_DIR        where engine writes its session-end scoring.yaml
# Optional:
#   AIC_V2_FPS             default 20
#   AIC_V2_JPG_QUALITY     default 85
#   AIC_V2_CAMERA_H/W      default 256, 256
#   AIC_V2_GAZEBO_GUI      "true" / "false" (default false)
#   AIC_V2_LAUNCH_RVIZ     "true" / "false" (default false)
#   AIC_V2_REPO_ROOT       absolute path to repo root inside container
#   AIC_V2_LOG_DIR         where to write component logs (default $AIC_V2_OUTPUT_DIR/logs)

set -euo pipefail

# Resolve REPO_ROOT: explicit env var wins; else compute from this script's location.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
REPO_ROOT="${AIC_V2_REPO_ROOT:-$( cd "$SCRIPT_DIR/../.." && pwd )}"
RECORDER_PKG_DIR="$REPO_ROOT/data_collection_v2/recorder"

: "${AIC_V2_SESSION_YAML:?must be set}"
: "${AIC_V2_TRIAL_CONFIGS:?must be set}"
: "${AIC_V2_OUTPUT_DIR:?must be set}"
: "${AIC_RESULTS_DIR:?must be set}"

mkdir -p "$AIC_V2_OUTPUT_DIR"
mkdir -p "$AIC_RESULTS_DIR"

LOG_DIR="${AIC_V2_LOG_DIR:-$AIC_V2_OUTPUT_DIR/logs}"
mkdir -p "$LOG_DIR"

FPS="${AIC_V2_FPS:-20}"
JPG_QUALITY="${AIC_V2_JPG_QUALITY:-85}"
CAMERA_H="${AIC_V2_CAMERA_H:-256}"
CAMERA_W="${AIC_V2_CAMERA_W:-256}"
GAZEBO_GUI="${AIC_V2_GAZEBO_GUI:-false}"
LAUNCH_RVIZ="${AIC_V2_LAUNCH_RVIZ:-false}"
MODEL_DISCOVERY_TIMEOUT="${AIC_V2_MODEL_DISCOVERY_TIMEOUT:-120}"
POLICY_CLASS="${AIC_V2_POLICY:-aic_example_policies.ros.CheatCode}"

# Source the workspace overlay so ros2 + the AIC packages are on PATH.
# Lift `set -u` around the source: /ws_aic/install/setup.bash references
# COLCON_TRACE without checking, which trips strict mode.
if [[ -f /ws_aic/install/setup.bash ]]; then
  set +u
  # shellcheck disable=SC1091
  source /ws_aic/install/setup.bash
  set -u
fi

# Make our recorder Python package importable. We deliberately do NOT colcon-build
# it (would add a build step + a second image). Two entries:
#   $RECORDER_PKG_DIR — lets `python3 -m data_collection_v2_recorder.recorder_node` resolve.
#   $REPO_ROOT       — lets `import data_collection_v2.pipeline...` resolve (data_collection_v2
#                       lives directly inside the repo root, so the repo root must be on
#                       sys.path, NOT its parent).
export PYTHONPATH="$RECORDER_PKG_DIR:$REPO_ROOT:${PYTHONPATH:-}"

# Ensure pyarrow + opencv-python are available. The aic_eval image ships
# python3-opencv via apt, but pyarrow needs pip — and pip itself is missing
# from the base image. So: apt -> python3-pip, then pip --break-system-packages -> pyarrow.
# We run as root inside aic_eval; --break-system-packages installs to the
# container's system site-packages, NOT to /home/smohite/.local on the host
# bind mount. Idempotent: skips entirely if pyarrow already imports.
if ! python3 -c "import pyarrow" >/dev/null 2>&1; then
    echo "[v2_entrypoint] pyarrow missing — installing..."
    if ! python3 -m pip --version >/dev/null 2>&1; then
        echo "[v2_entrypoint] python3 pip not present; apt install python3-pip..."
        apt-get install -y --no-install-recommends python3-pip >/dev/null
    fi
    python3 -m pip install --break-system-packages --quiet pyarrow
fi

if ! python3 -c "import cv2" >/dev/null 2>&1; then
    echo "[v2_entrypoint] cv2 missing — installing opencv-python-headless via pip..."
    if ! python3 -m pip --version >/dev/null 2>&1; then
        apt-get install -y --no-install-recommends python3-pip >/dev/null
    fi
    python3 -m pip install --break-system-packages --quiet opencv-python-headless
fi

# RMW + Zenoh config — match docker/aic_eval defaults.
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_zenoh_cpp}"
export ZENOH_ROUTER_CHECK_ATTEMPTS="${ZENOH_ROUTER_CHECK_ATTEMPTS:--1}"

PIDS=()
cleanup() {
  echo "[v2_entrypoint] cleanup: tearing down PIDs ${PIDS[*]:-none}"
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill -TERM "$pid" 2>/dev/null || true
    fi
  done
  sleep 1
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill -KILL "$pid" 2>/dev/null || true
    fi
  done
  # Belt-and-braces: zenoh routers like to outlive their parents
  pkill -9 -f rmw_zenohd 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# 1. Zenoh router.
echo "[v2_entrypoint] starting rmw_zenohd..."
ros2 run rmw_zenoh_cpp rmw_zenohd >"$LOG_DIR/zenoh.log" 2>&1 &
PIDS+=("$!")

# Give the router a moment to bind to tcp/[::]:7447 before peers try to connect.
sleep 2

# 1b. Rosbag cleaner — aic_engine writes ~1 GB per trial to engine_results/
# for tier-2 scoring. Once tier-2 has read the bag, it's dead weight (and
# 1500 trials × 1 GB ≈ 1.5 TB). We can't disable bag recording without
# breaking tier-2, so we delete bags AFTER tier-2 finishes with them.
#
# Heuristic: keep only the two most-recent bag dirs. The newest is the
# in-flight trial; the second-newest is the just-finished trial whose
# tier-2 scoring may still be running. Older bags have been scored and
# are safe to delete.
#
# Why not -mmin: directory mtime is set at creation, not updated as
# `.mcap` files inside grow, so a 60s mtime check deletes live bags
# while a trial is still running (observed 2026-05-14: tier_2 mean
# collapsed from 16.6 → 4.2 because the cleaner raced the writer).
echo "[v2_entrypoint] starting rosbag cleaner (keeps 2 newest bags)..."
(
    while true; do
        ls -1dt "$AIC_RESULTS_DIR"/bag_trial_* 2>/dev/null \
            | tail -n +3 \
            | xargs -r rm -rf 2>/dev/null || true
        sleep 30
    done
) &
PIDS+=("$!")

# 2. aic_model with the configured policy.
echo "[v2_entrypoint] starting aic_model (policy=$POLICY_CLASS)..."
ros2 run aic_model aic_model \
    --ros-args \
    -p use_sim_time:=true \
    -p policy:="$POLICY_CLASS" \
    >"$LOG_DIR/model.log" 2>&1 &
PIDS+=("$!")

# 3. Recorder.
echo "[v2_entrypoint] starting recorder..."
python3 -m data_collection_v2_recorder.recorder_node \
    --ros-args \
    -p use_sim_time:=true \
    -p output_dir:="$AIC_V2_OUTPUT_DIR" \
    -p trial_configs:="$AIC_V2_TRIAL_CONFIGS" \
    -p fps:="$FPS" \
    -p image_jpg_quality:="$JPG_QUALITY" \
    -p camera_h:="$CAMERA_H" \
    -p camera_w:="$CAMERA_W" \
    >"$LOG_DIR/recorder.log" 2>&1 &
PIDS+=("$!")

# Give model + recorder a beat to subscribe before the engine starts firing
# transitions and observations.
sleep 3

# 4. Engine — foreground; blocks until all trials complete (or engine errors).
# We do NOT `exec` here because we want step 5 (finalize) to run after the engine.
echo "[v2_entrypoint] launching aic_bringup with start_aic_engine:=true..."
echo "[v2_entrypoint]   session yaml : $AIC_V2_SESSION_YAML"
echo "[v2_entrypoint]   results dir  : $AIC_RESULTS_DIR"

set +e
ros2 launch aic_bringup aic_gz_bringup.launch.py \
    gazebo_gui:="$GAZEBO_GUI" \
    launch_rviz:="$LAUNCH_RVIZ" \
    ground_truth:=true \
    start_aic_engine:=true \
    shutdown_on_aic_engine_exit:=true \
    aic_engine_config_file:="$AIC_V2_SESSION_YAML" \
    model_discovery_timeout_seconds:="$MODEL_DISCOVERY_TIMEOUT"
ENGINE_RC=$?
set -e
echo "[v2_entrypoint] engine exited with rc=$ENGINE_RC"

# 5. Finalize the LeRobot v2 dataset from inside the container.
#    The container writes parquet/jsonl files as root; the host can't overwrite
#    them, so info.json + stats.json must be produced here. Idempotent — safe
#    to re-run.
echo "[v2_entrypoint] finalizing LeRobot v2 dataset..."
python3 - <<PY
import sys
sys.path.insert(0, "$REPO_ROOT")
from data_collection_v2.pipeline.lerobot_v2_writer import WriteSession
ws = WriteSession(
    root="$AIC_V2_OUTPUT_DIR/lerobot_v2",
    fps=$FPS,
    camera_hw=($CAMERA_H, $CAMERA_W),
)
ws.finalize()
print("[v2_entrypoint] dataset finalized (info.json + stats.json written)")
PY

exit $ENGINE_RC
