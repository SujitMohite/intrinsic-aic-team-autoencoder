# Baseline Policies

All in [`aic_example_policies/aic_example_policies/ros/`](../../aic_example_policies/aic_example_policies/ros/). Each lives at `aic_example_policies.ros.<Name>` for the `policy` ROS parameter.

| Policy | Purpose | Useful for us |
| --- | --- | --- |
| [`WaveArm.py`](../../aic_example_policies/aic_example_policies/ros/WaveArm.py) | Waves the arm back and forth via Cartesian pose targets | Smoke-test that pixi env, lifecycle, and Zenoh are working |
| [`CheatCode.py`](../../aic_example_policies/aic_example_policies/ros/CheatCode.py) | Uses **ground-truth TF** to look up plug + port pose, PID approach | The **scoring ceiling** for hand-engineered solutions; reference number for our learned policy |
| [`RunACT.py`](../../aic_example_policies/aic_example_policies/ros/RunACT.py) | Loads an ACT (Action Chunking with Transformers) model from HuggingFace | **The closest baseline to our autoencoder approach.** Read it carefully — it shows how to load `torch` lazily, process images with cv2, and bridge LeRobot policies to ROS |
| [`SpeedDemon.py`](../../aic_example_policies/aic_example_policies/ros/SpeedDemon.py) | High stiffness, low damping → high jerk → low Tier 2 smoothness | Stress-tests the force penalty (it presses) |
| [`GentleGiant.py`](../../aic_example_policies/aic_example_policies/ros/GentleGiant.py) | Low stiffness, high damping → smooth motion → high Tier 2 smoothness | Demonstrates the jerk-vs-Tier3 trade-off |
| [`WallToucher.py`](../../aic_example_policies/aic_example_policies/ros/WallToucher.py) | Joint-mode policy that extends the arm into the enclosure wall | Exercises the off-limit penalty |
| [`WallPresser.py`](../../aic_example_policies/aic_example_policies/ros/WallPresser.py) | Joint-mode policy that presses on the wall | Exercises the force penalty |

## Expected scores

From [`docs/scoring_tests.md`](../../docs/scoring_tests.md):

| Policy | Tier 1 | Tier 2 highlights | Tier 3 |
| --- | --- | --- | --- |
| (no model) | fail | — | — |
| WaveArm | pass | smoothness ok, no duration/efficiency (no proximity) | 0 |
| CheatCode | pass | smoothness, duration, efficiency all max | 60 (success) per trial |
| GentleGiant | pass | none (no proximity) | 0 |
| SpeedDemon | pass | force penalty −12 | 0 |
| WallToucher | pass | off-limit penalty −24 | 0 |
| WallPresser | pass | force −12 (often + off-limit) | 0 |

> Tier 3 values upstream use older 0-60 scale; current `docs/scoring.md` says 0-75 for full insertion. Cross-check `scoring.yaml` after a run.

## Running a baseline (always 3 terminals)

```bash
# Terminal 0: Zenoh router (if not using distrobox)
ros2 run rmw_zenoh_cpp rmw_zenohd

# Terminal 1: our model
pixi run ros2 run aic_model aic_model --ros-args \
  -p use_sim_time:=true \
  -p policy:=aic_example_policies.ros.CheatCode

# Terminal 2: simulation + engine
AIC_RESULTS_DIR=~/aic_results/cheatcode \
  ros2 launch aic_bringup aic_gz_bringup.launch.py \
    ground_truth:=true \
    start_aic_engine:=true
```

(or, equivalently for routing, enter the eval container in Terminal 0 and run `/entrypoint.sh ground_truth:=true start_aic_engine:=true` — that bundles the router + sim).

## Reading CheatCode

`CheatCode.py` is what most of us start with for a sanity check. Key things to notice:
- It looks up plug + port poses from `/tf` ground-truth (only available when `ground_truth:=true`).
- It computes the SE(3) error and runs PID on it.
- It uses `MODE_POSITION` Cartesian targets.
- **Will fail at eval** because `/scoring/tf` is off-limits. It's a debugging benchmark only.

## Reading RunACT

`RunACT.py` is our closest reference for an ML policy:
- Imports `torch`, `draccus`, `huggingface_hub` **inside the policy** (not at module top — keeps discovery under 30 s).
- Pulls a checkpoint via `huggingface_hub.snapshot_download`.
- Decodes images with `cv2`.
- Treats the policy as a sequence-to-sequence transformer that emits action chunks.
- Bridges to `move_robot` by converting transformer outputs into `MotionUpdate` messages.

If our autoencoder approach piggybacks on LeRobot, RunACT is the closest template.
