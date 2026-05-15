# CLAUDE.md — AI for Industry Challenge (Team Autoencoder)

> Read this first. It is the operating manual for any agent (Claude, Cursor, etc.) working in this repo.
> Detailed, modular reference docs live in [`context/`](./context/). Start there for any phase-specific work.

---

## 1. What this repo is

This is the team-autoencoder fork of `intrinsic-dev/aic` — the **AI for Industry Challenge** toolkit (Intrinsic + NVIDIA + Google DeepMind). The competition asks participants to train a robot policy that performs **dexterous cable insertion** (SFP and SC fiber-optic plugs into ports on a randomized task board) using a UR5e + Robotiq Hand-E in **Gazebo (ROS 2 Kilted)**. Three phases: Qualification (sim only) → Phase 1 (Flowstate) → Phase 2 (real robot). $180K prize pool.

We are currently focused on **Qualification Phase** (3 trials, max 300 points). The team approach is **autoencoder-based** representation learning — see [`context/07_team/00_approach.md`](./context/07_team/00_approach.md).

---

## Current state (2026-05-14): keystone data collection ready to launch

- `data_collection_v2/` pipeline is **built and validated**. Uses a forked policy `data_collection_v2.policy.FastCheatCode` (TF-based early-exit fork of upstream CheatCode).
- **DR envelope was narrowed** after empirical testing: open-loop CheatCode is fragile to wide grasp/yaw randomization. Current keystone DR (in `configs/keystone_{a,b}.yaml`): nic_yaw ±0.08 rad (½ doc-spec), grasp_rpy σ=0.02 rad (½ doc-spec), board_yaw π±0.3 rad.
- **Filter-on-train is mandatory**. FastCheatCode raw output has ~⅔ low-quality demos. Filter `manifest.jsonl` rows where `scoring.total ≥ 70` (or 85 for top-15 quality). See [`context/04_training/05_keystone_dataset.md`](./context/04_training/05_keystone_dataset.md).
- Two-machine parallel collection plan: [`context/07_team/05_keystone_playbook.md`](./context/07_team/05_keystone_playbook.md). 500-trial half on this machine, 1000-trial half on the faster laptop, USB-rsync to consolidate.
- First training pass recipe (ACT on filtered subset): [`context/04_training/07_first_pass_recipe.md`](./context/04_training/07_first_pass_recipe.md).

## 2. Top-of-mind facts (don't relearn these)

- **ROS distro:** ROS 2 **Kilted Kaiju**. Other distros are not guaranteed to interoperate.
- **Middleware:** `rmw_zenoh_cpp` (set by `pixi_env_setup.sh`).
- **Pkg manager:** `pixi` — **must** be `0.67.2` (pinned in `docker/aic_model/Dockerfile:4`). Run `pixi self-update --version 0.67.2` if unsure.
- **Container manager for distrobox:** `docker` — `export DBX_CONTAINER_MANAGER=docker` before `distrobox enter`.
- **Eval image:** `ghcr.io/intrinsic-dev/aic/aic_eval:latest` (do not rebuild unless using `docs/build_eval.md`).
- **Sim time:** Always use the ROS clock inside policies (`self.get_clock()`, `self.sleep_for(...)`), NOT `time.time()`/`time.sleep()`. Time limits are measured in sim time.
- **Discovery budget:** 30 s from container start to discoverable `aic_model` node. **Heavy imports (torch, transformers) must go inside `insert_cable()`, not at module top level.**
- **Lifecycle:** `aic_model` must be a ROS 2 LifecycleNode named `aic_model`. No publishing in `unconfigured` or `configured`. See [`context/03_policy/01_lifecycle_contract.md`](./context/03_policy/01_lifecycle_contract.md).
- **Tare service** (`/aic_controller/tare_force_torque_sensor`) is **unavailable during evaluation** — do not call it from the policy.
- **Trials at evaluation:** the published `sample_config.yaml` uses NIC cards 0 and 1, but **the board supports 0–4**. Test against all 5 to avoid hard-coded assumptions.

---

## 3. Repository map

```
aic_adapter/          ROS adapter — sensor fusion, sync, builds Observation
aic_assets/           3D models (SFP/SC/LC/NIC, cables, task board, robot, enclosure)
data_collection_v2/   ★ KEYSTONE DATA PIPELINE — FastCheatCode-based collection
                      configs/{smoke,coverage,yaw_sweep,mini_keystone,keystone_a,keystone_b}.yaml
                      policy/FastCheatCode.py (TF early-exit fork of upstream CheatCode)
                      pipeline/coverage.py (12-combo + yaw-sweep enumerators)
                      session_driver.py + cli.py + container/v2_entrypoint.sh
aic_bringup/          Launch files (aic_gz_bringup.launch.py is the main one)
aic_controller/       Cartesian + joint impedance controller (C++, runs at ~500 Hz)
aic_description/      URDF/SDF (UR5e + Robotiq Hand-E + task board + aic.sdf world)
aic_engine/           Trial orchestrator + sample_config.yaml
aic_example_policies/ Baselines: WaveArm, CheatCode, RunACT, SpeedDemon, GentleGiant, WallToucher, WallPresser
aic_gazebo/           Custom Gazebo plugins (off-limit contacts, etc.)
aic_interfaces/       Msgs/Srvs/Actions:
  ├── aic_task_interfaces/        Task.msg, InsertCable.action
  ├── aic_model_interfaces/       Observation.msg
  ├── aic_control_interfaces/     MotionUpdate, JointMotionUpdate, ChangeTargetMode
  └── aic_engine_interfaces/      engine-side srvs
aic_model/            PARTICIPANT ENTRY POINT — Policy ABC + LifecycleNode wrapper
aic_scoring/          Tiered scoring implementation
aic_utils/
  ├── aic_training_interfaces/    /expand_xacro for programmatic spawning
  ├── aic_training_utils/         Training launch helpers
  ├── aic_teleoperation/          Keyboard teleop (joint + Cartesian)
  ├── aic_isaac/                  Isaac Lab integration (NVIDIA)
  ├── aic_mujoco/                 MuJoCo integration (DeepMind)
  └── lerobot_robot_aic/          LeRobot adapter (imitation learning)
docker/               aic_eval / aic_model / rmw_zenohd + docker-compose.yaml
docs/                 Upstream documentation (do not edit — see context/ for our notes)
context/              ★ Team-local context, organized by phase + task type
pixi.toml             Workspace deps; pixi_env_setup.sh sets RMW + ZENOH overrides
```

---

## 4. Where to look for what

| You want to… | Read first |
| --- | --- |
| Understand the challenge | [`context/00_challenge/`](./context/00_challenge/) |
| Set up locally / spin up the eval container | [`context/01_environment/00_setup.md`](./context/01_environment/00_setup.md) |
| Know the ROS surface (topics / msgs) | [`context/02_interfaces/`](./context/02_interfaces/) |
| Write or modify a policy | [`context/03_policy/`](./context/03_policy/) |
| Train (LeRobot / Isaac / MuJoCo / teleop) | [`context/04_training/`](./context/04_training/) |
| Score locally / debug a regression | [`context/05_evaluation/`](./context/05_evaluation/) |
| Submit | [`context/06_submission/`](./context/06_submission/) |
| Look up a term | [`context/08_reference/00_glossary.md`](./context/08_reference/00_glossary.md) |
| Track team decisions / experiments | [`context/07_team/`](./context/07_team/) |
| Compare methods (classical / IL / RL / VLA / hybrid) | [`context/09_methods/00_index.md`](./context/09_methods/00_index.md) |
| Pick a data-collection strategy | [`context/10_data/00_index.md`](./context/10_data/00_index.md) |
| Design the autonomous research loop | [`context/10_data/12_auto_research_loop.md`](./context/10_data/12_auto_research_loop.md) |
| **Run the keystone data collection** | [`context/07_team/05_keystone_playbook.md`](./context/07_team/05_keystone_playbook.md) |
| **Understand the keystone dataset for training** | [`context/04_training/05_keystone_dataset.md`](./context/04_training/05_keystone_dataset.md) |
| **Test a trained policy locally** | [`context/04_training/06_local_eval_loop.md`](./context/04_training/06_local_eval_loop.md) |
| **Start the first training pass** | [`context/04_training/07_first_pass_recipe.md`](./context/04_training/07_first_pass_recipe.md) |

The numeric prefix on each subfolder reflects reading order for a new teammate.

---

## 5. Hard rules — DO NOT cross these

Violating any of these causes disqualification (see [`docs/challenge_rules.md`](./docs/challenge_rules.md)):

1. **No direct state manipulation.** Don't read `/tf` ground-truth, spawn/despawn entities, pause physics, or write to `/scoring`, `/gazebo`, `/gz_server`, `/clock`, `/world_stats`, etc. **at evaluation time**. (Ground truth is fine during training.)
2. **No bypassing `aic_model` interfaces.** Only publish on `/aic_controller/pose_commands` or `/aic_controller/joint_commands`. Only consume the observations exposed by `aic_adapter`.
3. **No hardcoding for the sample config.** Board pose, NIC rail selection, port choice are randomized at eval.
4. **No tampering with the lifecycle.** Don't publish in `unconfigured`/`configured`/`shutdown`. Don't refuse `cancel`. Don't run beyond `task.time_limit`.
5. **No fast/dirty submissions.** Always verify locally via `docker compose -f docker/docker-compose.yaml up` first — the portal counts failed pulls against your daily quota.

---

## 6. Daily workflow

### Spin up sim + run a baseline
```bash
# Terminal A: eval container
export DBX_CONTAINER_MANAGER=docker
distrobox enter -r aic_eval
/entrypoint.sh ground_truth:=false start_aic_engine:=true

# Terminal B: a policy (outside distrobox is easier)
cd ~/ws_aic/src/intrinsic-aic-team-autoencoder
pixi run ros2 run aic_model aic_model --ros-args \
  -p use_sim_time:=true \
  -p policy:=aic_example_policies.ros.CheatCode
```
Results land in `~/aic_results/scoring.yaml` (override with `AIC_RESULTS_DIR=...`).

### Iterate on our own policy
1. Add or modify a `Policy` subclass under our package (we will create one — see `context/03_policy/03_writing_a_policy.md`).
2. `pixi reinstall <our_pkg>` after every change (pixi does not auto-track).
3. Run as above with `-p policy:=<module_path>.<ClassName>`.

### Submit
See [`context/06_submission/`](./context/06_submission/). Tags in ECR are immutable — always bump the version.

---

## 7. Agent etiquette (Claude-specific)

- **Don't touch `docs/`.** That's upstream — keep our notes in `context/`. If upstream changes, we want a clean diff.
- **Don't edit core pkgs (aic_engine, aic_controller, aic_scoring, aic_interfaces)** without a justified reason; we should win by writing a better policy, not by patching the harness.
- **Pixi is slow.** Don't run `pixi install` casually. Prefer `pixi reinstall <pkg>` after editing a single package.
- **Use `rg`/`grep` before `pixi run`.** Searching is free; spinning environments is not.
- **Sim time everywhere.** Any sleep, deadline, or timestamp in policy code must use the ROS clock.
- **Heavy ML imports go inside `insert_cable`.** Class `__init__` blocks lifecycle queries; keep it light.
- **When unsure between Cartesian and joint control,** the controller defaults to Cartesian (mode 1). Switch via `/aic_controller/change_target_mode` before sending joint commands.
- **Track experiments** in `context/07_team/02_experiments.md` so we can compare scoring.yaml outputs side by side.

---

## 8. Useful shortcuts

```bash
# Where am I in pixi?
pixi shell                       # enter env
pixi run -- <cmd>                # one-shot in env

# Run the controller in joint mode for a teleop check
ros2 service call /aic_controller/change_target_mode \
  aic_control_interfaces/srv/ChangeTargetMode "{target_mode: {mode: 2}}"

# Inspect a Task at runtime
ros2 topic echo --once /tf       # sim frames (don't use at eval)
ros2 action list                 # confirm /insert_cable is up
ros2 lifecycle get /aic_model    # current state

# Tare F/T (training only — disabled at eval)
ros2 service call /aic_controller/tare_force_torque_sensor std_srvs/srv/Trigger
```

---

## 9. Resources

See [`context/07_team/03_resources.md`](./context/07_team/03_resources.md) for the full layout. TL;DR:

- **Desktop (Xeon + RTX 2000 Ada 16 GB)** — sm_89, matches eval cloud's L4. Primary box for sim, training, submission builds.
- **Laptop 1 (T1000 4 GB)** — below AIC min spec. Code editing / Git / docs only. Don't trust Gazebo scores from here.
- **Laptop 2 (RTX 4070)** — excluded per team preference.
- **Codex (unlimited)** — boilerplate, scaffolding, tests, sweeps.
- **Claude Code ($550, Opus 4.7 1M)** — architectural decisions, cross-file debugging, post-mortems. Avoid burning context window with whole-repo loads — load only relevant `context/` files per question.

## 10. Open questions / TODOs for the team

Tracked in [`context/07_team/01_decisions_log.md`](./context/07_team/01_decisions_log.md). High-level items:
- Pick a representation: autoencoder-on-images vs. autoencoder-on-multimodal-obs (see [`context/09_methods/17_repr_autoencoder.md`](./context/09_methods/17_repr_autoencoder.md) and [`18_repr_pretrained.md`](./context/09_methods/18_repr_pretrained.md)).
- Decide training stack: LeRobot/ACT, Isaac Lab + RSL-RL, or hybrid (see [`context/09_methods/00_index.md`](./context/09_methods/00_index.md) decision guide). **First pass = ACT** per [`context/04_training/07_first_pass_recipe.md`](./context/04_training/07_first_pass_recipe.md).
- Pre-stage a non-cheating fallback submission image on ECR before iterating on the AE policy.
- ~~Build the keystone data pipeline~~ **DONE** — see `data_collection_v2/` + [`context/07_team/05_keystone_playbook.md`](./context/07_team/05_keystone_playbook.md). Launch pending mini-keystone re-verification.
- ~~Decide whether to extend `aic_example_policies.ros.RunACT` or fork~~ **Forked** into `data_collection_v2/policy/FastCheatCode.py` for data collection. Training policy will live under `team_autoencoder/policy/` (TBD).
- Write the `data_collection_v2/scripts/build_filtered_dataset.py` merge utility before the first training run (see [`context/04_training/05_keystone_dataset.md`](./context/04_training/05_keystone_dataset.md) § "Building a merged LeRobot dataset").
- **Build the auto-research loop harness** ([`context/10_data/12_auto_research_loop.md`](./context/10_data/12_auto_research_loop.md)) — uses unlimited Codex.

## 11. Tentative top-3 method path

From [`context/09_methods/00_index.md`](./context/09_methods/00_index.md) (see that file for full reasoning):

1. **Diffusion Policy + Force-aware ACT** (parallel bets, same data) — files [`04`](./context/09_methods/04_il_diffusion_policy.md), [`06`](./context/09_methods/06_il_force_aware.md). Multimodal handling + native F/T fit.
2. **Hybrid classical → learned residual** — file [`21`](./context/09_methods/21_hybrid_classical_learned.md). Structurally safest path; ResiP-style 5%→99% on 0.2 mm published.
3. **HIL-SERL fine-tune** — file [`12`](./context/09_methods/12_rl_hil_serl.md). Closest published analog to our task (USB connector insertion at sub-mm).

All three feed from the same keystone data pipeline ([`context/10_data/02_offline_scripted_groundtruth.md`](./context/10_data/02_offline_scripted_groundtruth.md)).

---

*Last updated: 2026-05-14. Maintained alongside `context/` — keep both in sync when challenge details change.*
