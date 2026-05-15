# Scoring Examples

Source: [`docs/scoring_tests.md`](../../docs/scoring_tests.md).

Reproducible exercises that hit each scoring tier. Use them to validate that our local stack is configured the same as eval.

## Prereqs (one-time per terminal)

```bash
source ~/ws_aic/install/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
export ZENOH_ROUTER_CHECK_ATTEMPTS=-1
export ZENOH_CONFIG_OVERRIDE='transport/shared_memory/enabled=true;transport/shared_memory/transport_optimization/pool_size=536870912'
```

(If using pixi, `pixi shell` already does the equivalent.)

## Example 1 — Tier 1 fail (no model)

Tests that the engine fails Tier 1 when no policy is around.

```bash
# Terminal 0
ros2 run rmw_zenoh_cpp rmw_zenohd

# Terminal 1 (sim + engine, no model)
AIC_RESULTS_DIR=~/aic_results/no_model \
ros2 launch aic_bringup aic_gz_bringup.launch.py start_aic_engine:=true
```

Expect: discovery timeout, Tier 1 fails on all 3 trials, no Tier 2/3.

## Example 2 — CheatCode reference

Upper-bound benchmark. Uses ground-truth TFs.

```bash
# Terminal 0
ros2 run rmw_zenoh_cpp rmw_zenohd

# Terminal 1
ros2 run aic_model aic_model --ros-args -p use_sim_time:=true \
  -p policy:=aic_example_policies.ros.CheatCode

# Terminal 2
AIC_RESULTS_DIR=~/aic_results/cheatcode \
ros2 launch aic_bringup aic_gz_bringup.launch.py \
  ground_truth:=true start_aic_engine:=true
```

Expect: 3/3 trials pass Tier 1, smoothness/duration/efficiency near max, no penalties, Tier 3 success (~60–75 per trial).

## Example 3 — WaveArm (Tier 1 pass, Tier 2 partial, Tier 3 zero)

```bash
# Terminal 1
ros2 run aic_model aic_model --ros-args -p use_sim_time:=true \
  -p policy:=aic_example_policies.ros.WaveArm

# Terminal 2
AIC_RESULTS_DIR=~/aic_results/wavearm \
ros2 launch aic_bringup aic_gz_bringup.launch.py start_aic_engine:=true
```

Expect: Tier 1 pass, smoothness present (no jerk penalty), no Tier 3 → no duration/efficiency bonus, total ~1 + Tier-2-jerk.

## Example 4 — Off-limit contact (WallToucher)

```bash
# Terminal 1
ros2 run aic_model aic_model --ros-args -p use_sim_time:=true \
  -p policy:=aic_example_policies.ros.WallToucher

# Terminal 2
AIC_RESULTS_DIR=~/aic_results/wall_toucher \
ros2 launch aic_bringup aic_gz_bringup.launch.py \
  ground_truth:=true start_aic_engine:=true
```

Expect: −24 off-limit penalty, Tier 3 = 0.

## Example 5 — Force penalty (WallPresser)

```bash
# Terminal 1
ros2 run aic_model aic_model --ros-args -p use_sim_time:=true \
  -p policy:=aic_example_policies.ros.WallPresser

# Terminal 2
AIC_RESULTS_DIR=~/aic_results/wall_presser \
ros2 launch aic_bringup aic_gz_bringup.launch.py \
  ground_truth:=true start_aic_engine:=true
```

Expect: −12 force penalty (possibly also −24 off-limit).

## Example 6 — Smooth motion (GentleGiant)

Shows Tier 2 jerk component is computed even with no insertion (but is gated by Tier 3 > 0 — for jerk award).

```bash
ros2 run aic_model aic_model --ros-args -p use_sim_time:=true \
  -p policy:=aic_example_policies.ros.GentleGiant
```

## Example 7 — Aggressive motion (SpeedDemon)

Demonstrates the cost of low damping / high stiffness.

```bash
ros2 run aic_model aic_model --ros-args -p use_sim_time:=true \
  -p policy:=aic_example_policies.ros.SpeedDemon
```

## How we use these

1. Run all 7 once. Confirm scores match expectations.
2. Save results into `~/aic_results/baselines/` as a regression baseline.
3. After modifying anything in the env / pixi / docker stack, re-run CheatCode. Score should not change. If it does, our local setup drifted.

## Note on score ranges in docs

`docs/scoring.md` and `docs/scoring_tests.md` have slightly different ranges for some tiers (different toolkit versions). Trust the code & current `aic_scoring/` over either doc. Always inspect actual `scoring.yaml` output for our run.
