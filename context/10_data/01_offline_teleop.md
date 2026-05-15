# Manual Teleoperation Demos — benchmark only

## TL;DR

A human drives the robot through cable insertions using keyboard / spacemouse / VR teleop and records (obs, action) demos. Conceptually the cleanest training signal we can produce — captures **human strategies** for handling the contact phase that a scripted controller can't easily replicate. **But it's manual.** Per the user's directive, we treat this as a **benchmark / sanity-check baseline**, not the primary pipeline. Use to validate that 50–100 hand-collected demos let an IL method clear Tier 1 + reasonable Tier 3.

## What it produces

- **Format**: LeRobot parquet (same schema as auto-pipelines).
- **Modalities**: cameras, F/T, joints, action (Cartesian deltas from teleop input).
- **Per-episode metadata**: trial config (manually set), success flag (human-judged).
- **Size**: 10–30 demos / hour × 1 sec ~ 20 steps each → ~600 timesteps / hour.

## How automatic? — **manual**

Human-in-the-loop the entire time. No automation.

- Throughput on our desktop with keyboard teleop: ~10–30 episodes / hour (mostly limited by reset + scene-spawn overhead, not the human's speed).
- Spacemouse / VR teleop is faster + more natural for 6-DoF motions but requires hardware we may not have.

## Distribution properties

What it covers naturally: nothing — entirely depends on the human's discipline.

What it requires: a **session protocol** that systematically samples NIC index × plug type × board pose buckets. Without protocol, all demos cluster on the easiest NIC index.

Manual coverage of 5 × 2 × ~10 pose buckets = 100 distinct (NIC, plug, pose) configurations × 10 demos each = 1000 demos = **30–100 hours of human time.** A non-starter for one operator.

## Pipeline sketch

```
1. Launch eval container with start_aic_engine:=false, ground_truth:=true, attach_cable_to_gripper:=true.
2. Pick a config from a protocol checklist (NIC index, board pose, plug type, grasp-noise sample).
3. Spawn scene programmatically via /expand_xacro.
4. Tare F/T sensor.
5. Run lerobot-record (or our adapter) — starts logging at trigger.
6. Operator teleoperates via keyboard / spacemouse to insert the plug.
7. On insertion or abort, stop recording.
8. Repeat for next config.
```

Existing toolkit pieces:
- `aic_utils/aic_teleoperation/` — keyboard teleop for joint and Cartesian modes.
- `lerobot-record` via `lerobot_robot_aic` adapter — handles parquet output.
- Pre-tare / tare sequence via `std_srvs/Trigger` on `/aic_controller/tare_force_torque_sensor`.

What we'd *write*: a session-coordinator script that prompts the operator with the next config and orchestrates recording.

## Storage + naming convention

Same as [`02_offline_scripted_groundtruth.md`](./02_offline_scripted_groundtruth.md), in a separate folder:

```
/data/aic_demos_teleop/
├── manifest.json
└── episodes/<id>/{episode.parquet, metadata.json, scoring.yaml}
```

Naming: `tele_<operator>_<sim>_<plug>_<NIC>_<seed>.parquet`.

## Which methods consume this

| Method | How |
|---|---|
| [[il-bc]] (02) | Demos for vanilla BC |
| [[il-act]] (03) | Demos for ACT |
| [[il-diffusion-policy]] (04) | Demos for DP |
| [[il-vqbet]] (05) | Demos for VQ-BeT |
| [[il-force-aware]] (06) | F/T-aware variant especially benefits from human contact strategies |
| [[rl-hil-serl]] (12) | The "interventions" stream in HIL-SERL is literally human teleop |

Note: **only file 06 (force-aware) and 12 (HIL-SERL) get a unique advantage from teleop demos over scripted demos.** For the others, scripted demos are cheaper and broader. So we'd only invest in teleop demos if pursuing F/T-aware IL with a human-strategy signal, or HIL-SERL fine-tuning.

## Compute & time

- ~30 episodes / hour × ~1 hour of human attention before fatigue.
- Operator-hours dominate. Compute is free at this throughput.

## Quality gates

- Operator visually confirms successful insertion (don't rely on engine's scoring alone — Tier 3 partial scoring can succeed without "clean" insertions).
- Force trace is sane (no spikes from sloppy teleop overshooting into the board → off-limit contact).
- Action stream is smooth (no jerky keypress artifacts dominating the action distribution).
- All (NIC, plug, pose-bucket) combinations covered before declaring done.

## Failure modes (what goes wrong)

- **Operator fatigue → quality drift across the session.** Mitigation: 30-min sessions, multiple operators, random ordering of configs.
- **Coverage bias** — operators favor easy NIC indices unless the protocol forces variety.
- **Action distribution mismatch** vs. inference — the policy will produce smooth continuous outputs; teleop produces step-wise commands. Smooth the recorded actions in post-processing (Savitzky-Golay).
- **Sim time vs wall time** — teleop runs at 1.0 RTF; the policy will run at sim-dependent RTF on the eval node. Demo "feel" may differ; mostly OK because we don't optimize for time at training.

## Why we are NOT building this primary

User directive: **automatic, not manual.** Combined with:
- Tiny team / operator capacity.
- 50–100 demos is a thin training set for our generalization-hungry methods.
- Scripted CheatCode pipeline ([`02_offline_scripted_groundtruth.md`](./02_offline_scripted_groundtruth.md)) covers the same data shape with no human time at >10× throughput.

When this **does** make sense:
1. **As a 100-episode sanity baseline.** Train BC on 100 teleop demos, observe Tier 3, compare to BC trained on 100 scripted demos. Tells us whether human strategies are worth chasing.
2. **For HIL-SERL** (file `12`) which architecturally needs human interventions.
3. **For exotic / failure-recovery data** that CheatCode cannot easily produce (e.g., "what if grasp drifts mid-insertion?").

## Cross-refs

- Primary alternative (and our recommended path): [[offline-scripted-groundtruth]] ([`./02_offline_scripted_groundtruth.md`](./02_offline_scripted_groundtruth.md)).
- Required for full HIL-SERL: [[rl-hil-serl]] (file `12`).
- Augmentation layer: [[synthetic-dr]] ([`./08_synthetic_dr.md`](./08_synthetic_dr.md)).
