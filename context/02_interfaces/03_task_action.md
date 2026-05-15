# Task & InsertCable Action

Definitions:
- [`aic_task_interfaces/msg/Task.msg`](../../aic_interfaces/aic_task_interfaces/msg/Task.msg)
- [`aic_task_interfaces/action/InsertCable.action`](../../aic_interfaces/aic_task_interfaces/action/InsertCable.action)

## Task.msg

```
string id                  # unique trial ID
string cable_type          # "sfp_sc_cable"
string cable_name          # "sfp_sc"
string plug_type           # "sfp" or "sc"
string plug_name           # "sfp_module" or "sc_plug"
string port_type           # "sfp" or "sc"
string port_name           # "sfp_port_0" | "sfp_port_1" | "sc_port_0" | "sc_port_1"
string target_module_name  # "nic_card_0" .. "nic_card_4", or "sc_port_0"/"sc_port_1" itself for SC trial
uint64 time_limit          # seconds, measured against sim clock. Sample config: 180.
```

### How we read it

```python
def insert_cable(self, task, get_observation, move_robot, send_feedback):
    is_sfp = task.plug_type == "sfp"
    target_port = task.port_name
    parent = task.target_module_name
    deadline = self.time_now() + Duration(seconds=task.time_limit)
```

### What we never do

- Hardcode logic on a specific `target_module_name`. The Task tells us *which* NIC card; we don't get to pick.
- Trust `time.time()` for the deadline. Use sim time.

## InsertCable.action

```
# Goal
Task task

---
# Result
bool success
string message

---
# Feedback
string message
```

### When the action is fired

`aic_engine` sends an `InsertCable` goal at trial start, after the cable is in our gripper and the F/T is tared. Our `aic_model` node accepts the goal in its `active` state.

### What our policy returns

`insert_cable()` returns `bool`. The wrapper translates that to `Result.success` and adds a default `message`. We can also push intermediate strings via `send_feedback("...")` — those land in the trial logs and are useful for debugging.

### Cancellation

If `aic_engine` cancels (because time ran out, or for any other reason), the wrapper signals our policy via cancellation of the threaded `insert_cable` execution. **We should not block the action thread holding `move_robot()` calls indefinitely** — see `aic_model/aic_model.py:249-310` for the cancel monitoring loop.

Practical pattern:
```python
def insert_cable(self, task, get_observation, move_robot, send_feedback):
    deadline = self.time_now() + Duration(seconds=task.time_limit - 5)  # buffer
    while self.time_now() < deadline:
        obs = get_observation()
        # ... compute action ...
        move_robot(motion_update=update)
        self.sleep_for(0.1)
        if self._is_inserted(obs):
            return True
    return False
```

## Time limit reality

- `sample_config.yaml` sets `time_limit: 180` per trial.
- Scoring duration component caps at **60 s**, so anything past 60 s gives 0 duration bonus.
- Realistic target: < 30 s per trial.

## Implication for our policy

- Insertion completion isn't required to score — partial / proximity is fine.
- But Tier 2 positive components require Tier 3 > 0, so we **must** at least get close.
- A "give up early and stop moving" strategy still costs: we burned time, didn't get insertion or proximity, and got 0.
