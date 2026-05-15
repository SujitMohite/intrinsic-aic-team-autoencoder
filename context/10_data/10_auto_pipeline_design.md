# Auto Pipeline Design — Infrastructure for Fully-Automatic Data Collection

## TL;DR

The **infrastructure layer** that the keystone pipeline ([`./02_offline_scripted_groundtruth.md`](./02_offline_scripted_groundtruth.md)) and the online pipelines ([`./04`-`05`-`06`](./04_online_isaac_parallel.md)) sit on top of. A small Python orchestrator that launches sims, spawns scenes, runs policies, logs data, and tears down — without human intervention. Same pattern reused across collection and evaluation. Once built, drives both the keystone data collection and the autoresearch loop's eval harness.

## Why this lives in its own file

The same orchestration runs in 5+ contexts:
- Keystone CheatCode demo collection.
- Online RL rollouts (Gazebo).
- Self-supervised observation collection.
- AE/IL/RL eval (auto-research harness).
- Distribution-coverage sweeps.

Documenting the design once means a single implementation serves all of them.

## What it produces (the infrastructure itself)

A Python package, e.g. `team_autoencoder/pipeline/`, with:
- `orchestrator.py` — main loop.
- `launcher.py` — sim subprocess management.
- `recorder.py` — per-episode parquet writer.
- `sweep_config.py` — sweep grid / random sampler.
- `quality_gates.py` — automated dataset validation.

## Design principles

1. **One source of truth for trial config.** A YAML or pydantic config defines everything: which sim, which policy, NIC, plug, board pose, grasp noise, seed.
2. **Idempotent per-episode.** Each episode is a separate subprocess; failures don't poison subsequent episodes.
3. **Restart-friendly.** Resume from the last completed episode by reading the manifest.
4. **Sim-agnostic.** Same interface for Gazebo, Isaac, MuJoCo (subclass `Launcher`).
5. **Policy-agnostic.** Pass policy as a CLI argument (`-p policy:=...`) to `aic_model`.
6. **Single observability axis.** All episodes log to one structured log (JSON Lines) with the same fields.

## Pipeline contract

```python
@dataclass
class TrialConfig:
    sim: Literal["gazebo", "isaac", "mujoco"]
    policy: str            # "aic_example_policies.ros.CheatCode"
    nic_index: int | None
    plug_type: str         # "sfp" | "sc"
    port_name: str
    target_module: str
    task_board_pose: tuple
    grasp_noise: tuple
    seed: int
    time_limit_s: int

@dataclass
class TrialResult:
    config: TrialConfig
    valid: bool
    tier1: int
    tier2_components: dict
    tier3_score: int
    total_score: int
    episode_path: Path
    wall_clock_s: float
    failure_reason: str | None
```

## Pipeline sketch

```
orchestrator.py:
    sweep = SweepGenerator(coverage_target=...)
    for config in sweep:
        result = run_one_trial(config)
        manifest.append(result)
        if not result.valid:
            log("invalid", config, result.failure_reason)
        if total_episodes >= budget:
            break
    quality_gates.validate(manifest)

run_one_trial(config):
    launcher = make_launcher(config.sim)
    launcher.spawn_scene(config)
    launcher.tare_ft()
    launcher.start_policy(config.policy, time_limit_s=config.time_limit_s)
    result = wait_for_completion(timeout=config.time_limit_s + 30)
    launcher.teardown()
    return result
```

## Storage layout

```
/data/aic/
├── manifest.jsonl                   one line per trial
├── episodes/<id>/episode.parquet    one parquet per trial
├── episodes/<id>/scoring.yaml       engine output
└── logs/<date>/orchestrator.log
```

## Quality gates (run after each batch)

1. **Per-axis coverage** as per [`./09_distribution_design.md`](./09_distribution_design.md).
2. **Trial success rate** ≥ 90% (assuming a competent scripted policy).
3. **RTF mean** ≥ 0.6 (sim degradation alert).
4. **Disk usage** within bound (auto-rotate / archive old episodes).

## Engineering cost

- v1: ~3-5 person-days. Most cost in the Gazebo launcher (headless mode, deterministic spawning, reliable teardown).
- Reusable across all pipelines — amortized cost is low.

## Failure modes

- **Zenoh router lifecycle**: must start router *before* launching `aic_model`; tear down between trials cleanly.
- **Headless Gazebo silent failures**: process exits 0 but nothing was rendered. Mitigation: monitor a heartbeat topic.
- **Manifest corruption** under crash: use atomic file writes / append-only with checksums.
- **Disk-fill races**: parquet writer fills disk silently. Pre-flight check + auto-pause.

## Multi-instance scaling on the desktop

- Single-instance: ~50 ep/h in Gazebo.
- 2-instance: ~80 ep/h (RTF degrades).
- 3+ instance: diminishing returns; physics fidelity suffers.

Better: **one Gazebo instance + one CPU MuJoCo instance** for diversity, not raw parallelism.

## Cross-refs

- Driven by: [[auto-research-loop]] ([`./12_auto_research_loop.md`](./12_auto_research_loop.md)).
- Consumers (data collection): [[offline-scripted-groundtruth]] ([`./02`](./02_offline_scripted_groundtruth.md)), [[online-gazebo-auto]] ([`./05`](./05_online_gazebo_auto.md)), [[self-supervised-obs]] ([`./07`](./07_self_supervised_obs.md)).
- Distribution targets: [[distribution-design]] ([`./09_distribution_design.md`](./09_distribution_design.md)).
