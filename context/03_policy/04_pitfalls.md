# Pitfalls — Things That Silently Kill Submissions

Source: [`docs/troubleshooting.md`](../../docs/troubleshooting.md), [`docs/challenge_rules.md`](../../docs/challenge_rules.md). Distilled from production failure modes.

## 1. Heavy imports at module top level → discovery timeout

**Symptom:** Policy runs perfectly locally but fails on the portal with no logs and no scoring.yaml. Engine says model never appeared.

**Cause:** Loading `torch`, `transformers`, large checkpoints, or `huggingface_hub.snapshot_download` at the top of `MyPolicy.py`. The model-discovery budget is **30 s** from container start.

**Fix:** Move heavy imports + downloads **inside** `insert_cable()`. Cache the loaded model in `self._model` on first call.

```python
# BAD
import torch
from transformers import AutoModel
MODEL = AutoModel.from_pretrained("...")          # runs at import → blows 30 s

class MyPolicy(Policy):
    def insert_cable(self, *args, **kwargs):
        ...

# GOOD
class MyPolicy(Policy):
    def __init__(self, p):
        super().__init__(p)
        self._model = None

    def _lazy(self):
        if self._model is None:
            import torch                          # imported lazily
            from transformers import AutoModel
            self._model = AutoModel.from_pretrained("...")

    def insert_cable(self, *args, **kwargs):
        self._lazy()
        ...
```

## 2. `__init__` doing real work

The policy's `__init__` is called from inside the `configure` lifecycle transition. While it runs, `aic_engine` is **polling lifecycle state** and may decide our node has hung. Result: trial cancelled, Tier 1 fail.

**Rule:** `__init__` allocates attributes only. Defer everything else.

## 3. Wall-clock time inside the policy

**Symptom:** Policy works locally (RTF ≈ 1.0), times out on the portal (RTF can drift).

**Cause:** `time.time()`, `time.sleep(...)`, `datetime.now()`. Sim time and wall time decouple as RTF drops or the cluster slows.

**Fix:** Always:
- `self.time_now()` (sim-aware) for timestamps.
- `self.sleep_for(0.05)` for waits.
- `self.get_clock().now()` for absolute references.
- Run with `-p use_sim_time:=true`.

## 4. Hardcoded NIC card index

**Symptom:** Trial succeeds when `nic_card_0` is the target, crashes/empty actions when `nic_card_3` is.

**Cause:** Sample config locks NIC 0/1; we assumed those were the only ones. **The actual eval randomizes 0–4.**

**Fix:** Read `task.target_module_name` and use it. Run local sweeps with `nic_card_2_present:=true` (etc.) to verify generalization.

## 5. Subscribing to `/tf` for ground truth

**Symptom:** Local perfect score (with `ground_truth:=true`), zero score at eval.

**Cause:** Reading port/plug poses from `/tf` only works when ground truth is on. At eval, ground truth is off — those frames don't exist.

**Fix:** Either:
- Use **vision** (our autoencoder approach), or
- Use only **robot kinematics** (joint_states / controller_state TCP), with no scene assumptions.

`CheatCode.py` is a debugging aid, not a deployment template.

## 6. Stuck in a fast loop without `sleep_for`

**Symptom:** CPU pegged at 100%, controller floods, no insertion.

**Cause:** A `while True: move_robot(...)` with no rate limiter.

**Fix:** Always `self.sleep_for(0.05)` (or whatever rate). The controller smooths anyway; > 50 Hz doesn't help and can crowd the network.

## 7. Mode confusion (Cartesian vs Joint)

**Symptom:** Send a `JointMotionUpdate` and the robot ignores it.

**Cause:** Controller is in Cartesian mode. Even though `aic_model.move_robot()` auto-switches, doing this **mid-trial** can lose a command and trigger the controller's error-reset.

**Fix:** Decide your mode at the start and stick with it. If you must switch, send a known-safe pose first, wait for completion, then switch.

## 8. Stiffness flattening mistakes

```python
# BAD — passes a 6-vector where a 36-array is expected
MotionUpdate(target_stiffness=[90,90,90,50,50,50], ...)

# GOOD
MotionUpdate(target_stiffness=np.diag([90,90,90,50,50,50]).flatten(), ...)
```

Joint commands use a 6-vector. **Cartesian commands use a flattened 6×6.**

## 9. Calling tare during evaluation

Don't `ros2 service call /aic_controller/tare_force_torque_sensor` from the policy. It's a no-op (disabled) but raises noise in logs and could trigger an audit flag.

## 10. Pixi caching stale package code

**Symptom:** Edited `AePolicy.py`, behavior didn't change.

**Cause:** Pixi doesn't auto-rebuild local path deps.

**Fix:** `pixi reinstall ros-kilted-team-autoencoder` after every change. Or, for iteration, `pixi shell` then `pip install -e team_autoencoder/` — but note this bypasses pixi and may not survive into the Docker image.

## 11. Submitting with `start_aic_engine:=true` baked into the image

**Symptom:** Our model container hangs and the cloud reports "Failed".

**Cause:** Confusing the **eval** container (which starts the engine) with the **model** container (which only runs `aic_model`). Our submission must **not** try to launch the engine.

**Fix:** Our submission Dockerfile is based on `docker/aic_model/Dockerfile`, whose entrypoint is `ros2 run aic_model aic_model ...`. Don't change the entrypoint to anything that launches Gazebo or the engine.

## 12. ECR tag collision

ECR tags are **immutable**. `v1` can only be pushed once. Use `:v1`, `:v2`, ... or a commit SHA. Pushes with existing tags **fail silently** and the portal won't reflect a new submission.

## 13. RTX 50xx + locked PyTorch

`lerobot==0.5.1` pins an older PyTorch that doesn't support `sm_120`. On RTX 5090, add:

```toml
[pypi-options.dependency-overrides]
torch = ">=2.7.1"
torchvision = ">=0.22.1"
```

to `pixi.toml`. (Doesn't affect the eval cloud, which uses L4 / sm_89.)
