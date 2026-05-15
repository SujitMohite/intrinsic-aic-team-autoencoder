# Pre-Submission Checklist

Run through this **before every push** to ECR. We get 1 submission/day; failed attempts still count.

## Code-level

- [ ] Heavy imports (`torch`, `transformers`, `huggingface_hub`) are inside `insert_cable()`, not at module top.
- [ ] `__init__` does no I/O, no model loading, no network calls. Defer to first `insert_cable`.
- [ ] All sleeps use `self.sleep_for(...)` or `rclpy.duration.Duration`. **No** `time.sleep`, `time.time`, `datetime.now`.
- [ ] `self.time_now()` (or `self.get_clock().now()`) for any deadline.
- [ ] Policy reads `task.port_name` / `task.target_module_name` — no hardcoded NIC index.
- [ ] No subscription to `/scoring/*`, `/gazebo/*`, `/gz_server/*`, `/clock` (set), `/tf` for ground-truth poses.
- [ ] No service call to `/aic_controller/tare_force_torque_sensor` during the policy run.
- [ ] Both Cartesian and Joint command paths set `header.stamp = self._parent_node.get_clock().now().to_msg()` and a valid `frame_id`.
- [ ] Stiffness for `MotionUpdate` is the flattened **6×6** (36-array). For `JointMotionUpdate`, it's a **6-vector**.
- [ ] `insert_cable` exits within `task.time_limit` (cap the loop with a deadline computed from sim time at entry).
- [ ] Cancellation cooperative: no infinite tight loops without a `sleep_for` check.

## Container-level

- [ ] Submission Dockerfile based on `docker/aic_model/Dockerfile` (or equivalent zenoh peer entrypoint).
- [ ] Pixi pinned at `0.67.2`.
- [ ] `pixi install --locked` succeeds inside the image (use `pixi.lock` checked into our repo).
- [ ] Our policy package directory is COPIED in: `COPY team_autoencoder /ws_aic/src/aic/team_autoencoder`.
- [ ] Checkpoint files COPIED in (or generated at build time). `RUN` steps that download from HF Hub at runtime are **forbidden** for eval — no guaranteed network egress.
- [ ] `CMD` line points to our policy: `["--ros-args", "-p", "policy:=team_autoencoder.AePolicy", "-p", "use_sim_time:=true"]`.
- [ ] Entrypoint script does NOT start `aic_engine` or Gazebo. Only `ros2 run aic_model aic_model`.
- [ ] Container image size < 25 GB (lean is better; affects pull time on the eval node).

## Local verification

- [ ] `docker compose -f docker/docker-compose.yaml build model` succeeds.
- [ ] `docker compose -f docker/docker-compose.yaml up` runs all 3 trials.
- [ ] `scoring.yaml` is produced with `tier_1.validity == 1` on all trials.
- [ ] Score is at least as good as our most recent good submission. Regression → don't ship.
- [ ] Watched logs for warnings, especially: discovery timeouts, lifecycle warnings, controller error resets, lockless-clock warnings.

## Generalization smoke test

- [ ] Ran trials with `nic_card_2_present:=true` AND `nic_card_3_present:=true` AND `nic_card_4_present:=true` separately. All produced valid commands; at least proximity > 0.
- [ ] Ran trial 3 (SC) without crashing.
- [ ] Grasp pose perturbed by 2 mm / 0.04 rad (set in custom config) — still produces motion.

## ECR push

- [ ] AWS profile pointed at our team's account: `aws sts get-caller-identity` shows the expected ARN.
- [ ] `docker login` against the ECR registry succeeded (within last 12 hours).
- [ ] Image tag is **new** — never previously used in our ECR repo. Suggested: `<YYYYMMDD>-<short-sha>`.
- [ ] `docker push <full URI>:<tag>` showed `Pushed` for every layer.

## Portal registration

- [ ] Full URI (with `:tag`) copied verbatim into the submission form.
- [ ] Phase: **Qualification**.
- [ ] No second click while the status is **Queued** or **Running**.

## After submit

- [ ] Recorded in `context/07_team/02_experiments.md`: tag, commit SHA, hypothesis, expected vs actual score.
- [ ] If **Failed**: investigated logs (portal "View logs"); compare to `04_pitfalls.md`.

## Today

- [ ] **Submission window closes May 15 (tomorrow).** We have one push left for today and one for tomorrow if needed.
