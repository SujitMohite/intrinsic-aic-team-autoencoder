# AGENTS.md - Codex Operating Manual for Team Autoencoder

This file is the first thing Codex should read in this repository. It is a
compact operating manual for working on Team Autoencoder's fork of the AI for
Industry Challenge toolkit.

Codex uses the same shared project context as every other agent. Start with
[`context/README.md`](context/README.md), then load only the specific context
files needed for the task. The Claude-oriented manual remains in
[`CLAUDE.md`](CLAUDE.md), but `context/` is the shared source of truth.

## Mission

This repo targets the AI for Industry Challenge qualification phase: train a
robot policy for dexterous cable insertion in Gazebo using a UR5e arm and
Robotiq Hand-E gripper. The qualification task is sim-only and includes SFP and
SC fiber-optic plug insertion on a randomized task board.

The participant-owned surface is the model/policy side. The harness,
controller, engine, scoring, assets, and ROS interfaces are mostly upstream
infrastructure and should be treated as fixed unless the user explicitly asks
for a justified change.

Current team strategy:

- **Data pipeline built** (`data_collection_v2/`). FastCheatCode
  (`data_collection_v2.policy.FastCheatCode`) is the demonstrator — a TF-based
  fork of upstream CheatCode with an early-exit. Keystone launch pending mini
  re-verification; commands and DR rationale in
  [`context/07_team/05_keystone_playbook.md`](context/07_team/05_keystone_playbook.md).
- DR is **halved from doc-spec** (nic_yaw_offset ±0.08 rad, grasp_rpy σ=0.02,
  board yaw π±0.3) — CheatCode is open-loop and skids at wider envelopes.
- Training will run on a **filtered subset** (`scoring.total ≥ 70`, ~30-40 % of
  raw demos). See [`context/04_training/05_keystone_dataset.md`](context/04_training/05_keystone_dataset.md).
- First training pass = **ACT** on the filtered subset, target top-30. Recipe:
  [`context/04_training/07_first_pass_recipe.md`](context/04_training/07_first_pass_recipe.md).
- Local eval loop (test before portal submit):
  [`context/04_training/06_local_eval_loop.md`](context/04_training/06_local_eval_loop.md).
- Treat autoencoders or pretrained vision encoders as representation layers,
  not standalone policies.
- Keep a valid fallback policy path available while improving the learned
  policy.

## Hard Rules

- Use ROS 2 Kilted Kaiju assumptions unless a task explicitly says otherwise.
- Use the existing `aic_model.Policy` framework for participant policies.
- `aic_model` must remain a ROS 2 LifecycleNode named `aic_model`.
- Policies must use ROS sim time via node clocks and timers, not wall-clock
  sleeps or `time.time()` deadlines.
- Heavy ML imports and checkpoint loading must be lazy, preferably inside
  `insert_cable()`, so the node remains discoverable within the 30 second
  discovery budget.
- Do not rely on forbidden evaluation-time ground truth such as scoring frames,
  simulator state, direct Gazebo state, or hidden transforms.
- Do not publish before lifecycle activation or continue after cancel/shutdown.
- Do not hardcode the sample config. Evaluation may use NIC card indices 0-4,
  randomized board poses, and both SFP/SC task variants.
- Do not edit upstream `docs/`; team notes belong in `context/`.
- Do not edit `aic_engine`, `aic_controller`, `aic_scoring`, or
  `aic_interfaces` unless the user requests it and the reason is documented.

## Repository Map

- `aic_model/`: participant entrypoint and `Policy` abstraction.
- `aic_example_policies/`: reference policies including CheatCode, RunACT, and
  simple baselines.
- `aic_adapter/`: sensor fusion and `Observation` construction.
- `aic_controller/`: Cartesian and joint impedance control.
- `aic_engine/`: trial orchestration and sample configs.
- `aic_interfaces/`: ROS messages, services, and actions.
- `aic_scoring/`: scoring implementation.
- `aic_utils/`: training utilities, teleoperation, Isaac, MuJoCo, LeRobot.
- `data_collection/`: legacy team data pipeline (per-trial container spawn —
  superseded by v2).
- `data_collection_v2/`: ★ keystone data pipeline. FastCheatCode policy + CLI
  subcommands `smoke / coverage / yaw_sweep / session / resume / report`.
  Configs in `data_collection_v2/configs/`. Output is a LeRobot v2 dataset.
- `data_collection_codex/`: alt Codex-prepared collection workflow (independent
  of v2; runs in parallel without ROS namespace conflict only on a separate
  container).
- `context/`: shared team context, research notes, and task routing.

## Where To Look

Use [`context/README.md`](context/README.md) as the index. The fastest routing
map is:

- Challenge and rules: `context/00_challenge/`.
- Environment and task board: `context/01_environment/`.
- ROS inputs, outputs, and controller surface: `context/02_interfaces/`.
- Policy lifecycle, baselines, and policy-writing guidance: `context/03_policy/`.
- Training stacks: `context/04_training/`.
- Evaluation and scoring: `context/05_evaluation/`.
- Submission: `context/06_submission/`.
- Team approach, decisions, experiments, and resources: `context/07_team/`.
- Glossary and troubleshooting: `context/08_reference/`.
- Method research: `context/09_methods/`.
- Data strategies: `context/10_data/`.
- 24-hour execution strategy: `context/11_24h_strategy/`.
- Concrete implementation plans: `context/12_implementation/`.

For near-term work, these files matter most:

- Current approach: `context/07_team/00_approach.md`.
- Decisions: `context/07_team/01_decisions_log.md`.
- Experiments: `context/07_team/02_experiments.md`.
- Methods index: `context/09_methods/00_index.md`.
- Data index: `context/10_data/00_index.md`.
- Scripted data pipeline: `context/10_data/02_offline_scripted_groundtruth.md`.
- Auto-research loop: `context/10_data/12_auto_research_loop.md`.
- Data pipeline implementation design:
  `context/12_implementation/00_data_pipeline_design.md`.

If summaries and code disagree, inspect the source code before changing
behavior.

## Build And Run Notes

Prefer read-only inspection before expensive commands. Use `rg` and targeted
file reads before running Pixi, ROS, or Docker.

Common commands:

```bash
pixi shell
pixi run -- <cmd>
pixi reinstall <pkg>
```

Baseline policy run shape:

```bash
pixi run ros2 run aic_model aic_model --ros-args \
  -p use_sim_time:=true \
  -p policy:=aic_example_policies.ros.CheatCode
```

The evaluation stack is normally run through the provided Docker/distrobox
workflow documented in `context/01_environment/00_setup.md` and
`context/05_evaluation/00_local_eval.md`.

## Documentation Etiquette

- Use the existing `context/` tree for Codex as well; do not create a separate
  Codex-specific duplicate unless the user asks for one.
- Update `context/07_team/01_decisions_log.md` for material strategy changes.
- Update `context/07_team/02_experiments.md` when a run produces a meaningful
  score or failure pattern.
- Cross-link to detailed context instead of copying long passages.
- Preserve code links and line references when making claims about interfaces.

## Coding Etiquette

- Keep edits scoped to the user's task.
- Prefer existing project patterns over new abstractions.
- Use structured parsers for YAML, messages, and configs where practical.
- Do not commit datasets, checkpoints, generated episode files, or large logs.
- Store large generated datasets outside the repo, for example `/data/aic_demos`.
- Before touching policy logic, read the relevant baseline under
  `aic_example_policies/` and the policy docs under `context/03_policy/`.
