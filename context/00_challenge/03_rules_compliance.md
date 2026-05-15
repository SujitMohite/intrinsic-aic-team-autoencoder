# Rules & Compliance

Source: [`docs/challenge_rules.md`](../../docs/challenge_rules.md). Read upstream verbatim before submitting. This file is the operating summary.

## Prohibited at evaluation time

| Category | Examples | Why we'd be tempted |
| --- | --- | --- |
| **Direct state manipulation** | Reading `/tf` ground truth (`/scoring/tf`), teleporting models, forcing the cable into the port | Easy shortcut to a perfect score |
| **Backend interference** | Pausing physics, resetting world, modifying Gazebo entities | Bypass tough physics |
| **Simulation control topics** | `/scoring/*`, `/gazebo/*`, `/gz_server/*`, `/clock`, `/model`, `/world_stats`, `/pause_physics` | Influence scoring |
| **Lifecycle tampering** | Renaming nodes, refusing cancel, ignoring `time_limit`, publishing in `unconfigured`/`configured`/`shutdown` | Cheap timing wins |
| **Hardcoded scene knowledge** | `if nic_rail == 0: pose = (...)` | Avoid learning |
| **Container exploits** | Network egress, embedded keys, backdoors | Not relevant to us |

## What IS allowed during **training** (not eval)

- Use of `/tf` ground truth — see how `CheatCode.py` uses TFs.
- `start_aic_engine:=false` with manual scene control via `/expand_xacro` + `/gz_server/spawn_entity` (training utils).
- Custom scoring runs, custom configs, multi-sim domain randomization.

## What the eval system enforces

1. **Zenoh ACL** restricts which topics the participant container can subscribe to. See `docs/access_control.md` and [`../06_submission/02_checklist.md`](../06_submission/02_checklist.md).
2. **Container audit** of top-30 submissions — manual review.
3. **Behavioral verification** — engine logs the policy's pub/sub graph.
4. **Anomaly detection** on scores against expected baselines.

## `aic_model` behavioural contract

| State | Allowed | Disallowed |
| --- | --- | --- |
| `unconfigured` | none | publishing commands, accepting goals |
| `configured` | nothing on the wire | publishing commands, accepting goals |
| `active` | accept `InsertCable` goals, support cancel, publish commands | running past `task.time_limit` |
| `inactive` (after deactivate) | nothing on the wire | publishing |
| `shutdown` | none; publisher graph must be empty | any commands |

Each transition must complete within **60 s**. Discovery from container start must happen within **30 s**. See [`../03_policy/01_lifecycle_contract.md`](../03_policy/01_lifecycle_contract.md) for the implementation contract.

## Practical do/don't

- ✅ Subscribe to: cameras, F/T, joint_states, `/aic_controller/controller_state`, the Observation aggregate from `aic_adapter`.
- ✅ Publish to: `/aic_controller/pose_commands` or `/aic_controller/joint_commands`.
- ✅ Call: `/aic_controller/change_target_mode`.
- ❌ Subscribe to: anything under `/scoring`, `/gazebo`, `/gz_server`, `/clock` overrides.
- ❌ Call: `/aic_controller/tare_force_torque_sensor` during eval (the engine tares it before our cable spawns).
- ❌ Use: `time.time()`, `time.sleep()`. Use sim time only (`self.get_clock()`, `self.sleep_for(...)`).

## Reporting violations

If we suspect another team is cheating, report via the official channel (Open Robotics Discourse or the portal). We do not benefit from public accusations.

## Consequences

Disqualification + revocation of prizes. Manual review of top performers is policy. **Assume someone will read our container layer-by-layer.**
