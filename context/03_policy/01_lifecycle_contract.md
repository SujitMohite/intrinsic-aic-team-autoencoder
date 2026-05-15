# Lifecycle Contract

Source: [`docs/challenge_rules.md`](../../docs/challenge_rules.md) §4, [`aic_model/aic_model/aic_model.py`](../../aic_model/aic_model/aic_model.py).

The `aic_model` ROS 2 Lifecycle node must exhibit specific behaviour. Failure to comply = Tier 1 (Validity) failure = trial scores **zero**.

## Discovery

- After our container starts, the `aic_model` node must be **discoverable on the ROS graph within 30 s**.
- This is the `model_discovery_timeout_seconds` budget on the engine side.
- **What blows this budget:** heavy imports at module top level (torch, transformers, opencv with CUDA), large file reads, network downloads.

## States

| State | Allowed | Disallowed |
| --- | --- | --- |
| `unconfigured` | exist | publish any topic, especially commands |
| `configured` | exist | publish; accept `/insert_cable` goals |
| `active` | publish commands, accept goals, support cancel | run past `task.time_limit` |
| `inactive` | exist | publish |
| `shutdown` | exist briefly | publish; have command publishers in graph |

## Transition timeouts

| Transition | Must complete within |
| --- | --- |
| `configure` (unconfigured → configured) | **60 s** |
| `activate` (configured → active) | **60 s** |
| `deactivate` (active → configured) | **60 s** |
| `cleanup` (configured → unconfigured) | **60 s** |
| `shutdown` (any → shutdown) | **60 s** |

The provided `aic_model` wrapper handles transitions for us. Our hooks:

- `__init__` runs during `configure` (when `self.policy = PolicyClass(self)`). Keep light.
- `on_activate` only sets a flag; our class isn't touched.
- `on_cleanup` destroys our class.

## Goal handling

- In `configured`, goal requests to `/insert_cable` must be **rejected** by the action server. The wrapper does this.
- In `active`, goals are accepted; our `insert_cable()` runs in a thread.
- Goals must be **cancellable**. The wrapper monitors `goal_handle.is_cancel_requested` and signals us — but our policy must release `move_robot()` and exit `insert_cable()` promptly when cancel happens. Don't block on a busy loop without checking.

```python
def insert_cable(self, task, get_observation, move_robot, send_feedback):
    # Good: bounded by deadline, no infinite loops
    deadline_ns = self.time_now().nanoseconds + int(task.time_limit * 1e9)
    while self.time_now().nanoseconds < deadline_ns:
        ...
        self.sleep_for(0.05)
    return False
```

## Time-limit enforcement

`task.time_limit` is in **seconds of sim time**. Sim time can drift from wall time (RTF). Always use `self.get_clock().now()` (or `self.time_now()`) and `self.sleep_for()`.

## What gets us disqualified silently

- Heavy top-level imports → 30 s discovery exceeded → Tier 1 fail.
- Publishing in `configured` → wrapper test sees illegal topic → Tier 1 fail.
- Using `time.sleep()` → policy runs past `time_limit` when RTF < 1.0 → trial cancelled, no Tier 3.
- Refusing cancel → wrapper escalates to shutdown.

## Inspecting in development

```bash
ros2 lifecycle list                  # all lifecycle nodes
ros2 lifecycle get /aic_model        # current state
ros2 lifecycle set /aic_model configure   # manual transition
ros2 lifecycle set /aic_model activate
```

Useful while debugging — but at eval, the engine drives transitions automatically.
