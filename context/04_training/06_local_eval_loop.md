# Local eval loop — testing a trained policy against `aic_eval`

The `aic_eval` Docker image we have locally is **the same image organizers run**. Same engine, same scoring, same tier_1/2/3 computation. What's different is which trials get sampled — organizers keep their per-submission trial configs private and `aic_engine/config/sample_config.yaml` is a public template, not the exact eval trials. So a local run is a **calibration**, not a final score.

Source: [`CLAUDE.md`](../../CLAUDE.md) §6, [`docs/qualification_phase.md`](../../docs/qualification_phase.md), [`aic_engine/config/sample_config.yaml`](../../aic_engine/config/sample_config.yaml).

## When to use this

After training, before submitting to the portal — to catch:
- Catastrophic regressions (policy doesn't insert at all)
- Reward-hacking (policy scores high on training but low here)
- Lifecycle bugs (policy violates the `aic_model` contract)
- Tier-2 force-spike violations the manifest's reward doesn't catch

A good local-eval score is no guarantee of a good portal score, but a **bad** local score guarantees a bad portal score.

## The command

```bash
# Terminal A — eval container with ground_truth disabled (so the policy cannot
# peek at /tf for port positions).
export DBX_CONTAINER_MANAGER=docker
distrobox enter -r aic_eval
/entrypoint.sh ground_truth:=false start_aic_engine:=true
```

```bash
# Terminal B — your trained policy as an aic_model. Replace the policy arg.
cd ~/ws_aic/src/intrinsic-aic-team-autoencoder
pixi run ros2 run aic_model aic_model --ros-args \
    -p use_sim_time:=true \
    -p policy:=team_autoencoder.policy.YourTrainedPolicyClass
```

The policy class must be importable from PYTHONPATH and subclass `aic_model.policy.Policy`. See `data_collection_v2/policy/FastCheatCode.py` for a working example.

Output lands at `~/aic_results/scoring.yaml` (override with `AIC_RESULTS_DIR=...`). Format:

```yaml
trials:
  trial_1:
    tier_1: { score: 1, message: "Model validation succeeded." }
    tier_2: { score: 19.84 }
    tier_3: { score: 75.0,  message: "Cable insertion successful." }
    total: 95.84
  trial_2: { ... }
  trial_3: { ... }
total_score: 287.5
```

Three trials, total cap = 294. Leaderboard top-30 floor ≈ 176.

## What `ground_truth:=false` actually changes

With ground_truth on (the data-collection setting), `aic_adapter` publishes a TF tree that includes:
- `task_board/<module>/<port>_link` — exact port poses
- `<cable>/<plug>_link` — exact plug tip pose

FastCheatCode looks these up via `_parent_node._tf_buffer.lookup_transform(...)` to do its open-loop descent.

With ground_truth off (the eval setting):
- Those TF frames are NOT published
- The policy must localize the port from the wrist cameras and/or wrench
- `lookup_transform("base_link", "task_board/...", ...)` will raise `TransformException`

**This is why FastCheatCode cannot be tested locally with `ground_truth:=false`** — it would immediately fail the TF lookup. CheatCode-family policies are *data-collection only*.

## What a trained policy must NOT do

Hard rules from [`docs/challenge_rules.md`](../../docs/challenge_rules.md) (also surfaced in [`CLAUDE.md`](../../CLAUDE.md) §5):

1. **No `/tf` ground-truth lookups at eval time.** Use only `/observations`.
2. **No publishing to `/scoring`, `/gz_server`, `/gazebo`, `/clock`, or `/world_stats`.** Read-only is OK for `/scoring/insertion_event` if you really need it.
3. **No spawning, deleting, or repositioning entities.**
4. **Must remain a LifecycleNode named `aic_model`.** No publishing in `unconfigured` or `configured`.
5. **Time budget is enforced in sim time.** Use `self.sleep_for(...)` not `time.sleep(...)`.
6. **Heavy imports (torch, transformers) go inside `insert_cable`**, not module top-level — model discovery has a 30 s window.

The local eval enforces (1) by withholding ground-truth TFs and (4)/(5) by running the actual engine harness. (2), (3), (6) won't be caught locally but will fail at portal review.

## Interpreting the score

Per-trial cap is 1 + 22 + 75 = 98. The discriminator is **tier_2** (force/contact-stability score, 0–22 range computed from the rosbag) — top teams cluster at ~19–22.

- **tier_3 < 75** → cable physically didn't seat. Investigate that trial's wrench trace; usually a grasp/yaw misalignment the policy didn't correct.
- **tier_2 < 10** → force spikes during insertion (slammed into the port). Train the policy with explicit force-penalty signal or stronger smoothing.
- **tier_1 < 1** → conformance fail. Read `tier_1.message` — usually a lifecycle violation, late discovery, or publishing on a forbidden topic.

Match local scores against the training-set distribution: a policy trained on a filtered subset with mean total 90 should produce local-eval totals in the 70–80 range (IL teacher-student gap is typically 10–25 %).

## Submitting

When local eval is convincing, package the trained policy into a Docker image and submit via the portal. See [`context/06_submission/`](../06_submission/) for the build + tag + push steps. **Tags in ECR are immutable** — always bump the version.

Before pushing, verify locally with `docker compose -f docker/docker-compose.yaml up` from the repo root — that's the same harness the portal will use.
