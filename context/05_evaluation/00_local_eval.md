# Local Evaluation

Source: [`docs/scoring_tests.md`](../../docs/scoring_tests.md), [`aic_engine/README.md`](../../aic_engine/README.md), [`aic_engine/config/sample_config.yaml`](../../aic_engine/config/sample_config.yaml).

## Goal

Reproduce on our workstation what the cloud eval will do: 3 randomized trials, scored, results written to `scoring.yaml`. Use it to compare policies on identical seeds and to catch regressions before submitting.

## The standard 3-terminal layout

> Inside or outside distrobox; whichever is easier. Outside is faster to start, inside is closer to eval.

### Terminal 0 — Zenoh router (skip if using distrobox `/entrypoint.sh`)
```bash
ros2 run rmw_zenoh_cpp rmw_zenohd
```

### Terminal 1 — Our model
```bash
cd ~/ws_aic/src/intrinsic-aic-team-autoencoder
pixi run ros2 run aic_model aic_model --ros-args \
  -p use_sim_time:=true \
  -p policy:=team_autoencoder.AePolicy        # or aic_example_policies.ros.CheatCode
```

### Terminal 2 — Simulation + Engine
```bash
AIC_RESULTS_DIR=~/aic_results/run_$(date +%Y%m%d_%H%M%S) \
  ros2 launch aic_bringup aic_gz_bringup.launch.py \
    ground_truth:=false \
    start_aic_engine:=true
```

`ground_truth:=true` is fine for development; **set it to `false` to match eval conditions** before drawing conclusions.

## Watching it run

- Gazebo window: task board spawns, cable in gripper.
- Terminal 2 logs: "Trial 1/3 …", scoring banner per trial.
- Final summary lists each tier component for each trial.

## Engine parameters worth knowing

From `aic_engine/README.md`:

| Param | Default | Purpose |
| --- | --- | --- |
| `config_file_path` | sample_config.yaml | YAML defining trials, randomization, scoring |
| `model_node_name` | `aic_model` | What the engine looks for |
| `ground_truth` | `false` | Whether to enable scoring-namespace TFs |
| `model_discovery_timeout_seconds` | (varies) | Time to find our node |
| `model_configure_timeout_seconds` | 60 | Time to transition to configured |
| `model_activate_timeout_seconds` | 60 | Time to transition to active |
| `endpoint_ready_timeout_seconds` | (varies) | Time for endpoints to come up |

We can adjust these in our own config file for testing — never in submission, where the eval uses the published config.

## Customizing trials

Edit `aic_engine/config/sample_config.yaml` (or copy to `~/aic_my_config.yaml` and point `config_file_path` at it) to:

- Test NIC cards 2 / 3 / 4 (set `nic_card_X_present: true` and disable 0/1).
- Loosen `time_limit` while debugging.
- Lower randomization ranges to make a single failing trial reproducible.

Don't ship this — the eval uses the published config (or its successor).

## Headless mode

For batch runs / CI:

```bash
ros2 launch aic_bringup aic_gz_bringup.launch.py \
  start_aic_engine:=true headless:=true            # if supported by the launch file
```

Check `aic_bringup/README.md` for current args.

## Tooling around it

| Tool | Purpose |
| --- | --- |
| `ros2 topic hz /aic_controller/pose_commands` | Command rate sanity |
| `ros2 topic echo /insert_cable/feedback` | Live policy feedback |
| `ros2 topic echo /aic_controller/controller_state --once` | TCP pose snapshot |
| `ros2 lifecycle get /aic_model` | State debugging |
| `ros2 bag record -a -o run.bag` | Capture an entire run for offline analysis |

## Comparing runs

Set `AIC_RESULTS_DIR` differently for each run so `scoring.yaml` isn't overwritten:

```
~/aic_results/
├── cheatcode/scoring.yaml
├── wavearm/scoring.yaml
└── ae_v3/scoring.yaml
```

See [`02_results_files.md`](./02_results_files.md) for the schema.

## Docker-compose alternative (closest to eval)

```bash
docker compose -f docker/docker-compose.yaml up
```

This launches eval container + zenohd + our model container together. **This is the path the cloud uses.** If we pass here, we pass there.
