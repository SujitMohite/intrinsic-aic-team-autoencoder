# Policy Framework

Source: [`aic_model/aic_model/policy.py`](../../aic_model/aic_model/policy.py), [`aic_model/aic_model/aic_model.py`](../../aic_model/aic_model/aic_model.py), [`docs/policy.md`](../../docs/policy.md).

## The big picture

```
+-------------------------+        +---------------------+        +-----------------+
|  aic_engine (organizer) | -----> |  aic_model node     | -----> |  Our Policy     |
|  - fires InsertCable    |   ROS  |  - LifecycleNode    | py-load|  - inherits     |
|  - randomizes scene     |        |  - action server    |        |    aic_model.   |
|  - scores               |        |  - observation sub  |        |    Policy       |
+-------------------------+        +---------------------+        +-----------------+
```

The `aic_model` ROS node is provided. We supply a **Python class** named via the `policy` ROS parameter; `aic_model` dynamically imports it.

## The `Policy` ABC

[`aic_model/aic_model/policy.py`](../../aic_model/aic_model/policy.py):70

```python
class Policy(ABC):
    def __init__(self, parent_node): ...
    def get_logger(self): ...
    def get_clock(self): ...
    def time_now(self): ...
    def sleep_for(self, duration_sec: float) -> None: ...   # sim-time aware
    def set_pose_target(self, move_robot, pose, frame_id="base_link",
                        stiffness=[90,90,90,50,50,50],
                        damping=[50,50,50,20,20,20]) -> None: ...
    @abstractmethod
    def insert_cable(self, task, get_observation, move_robot, send_feedback) -> bool:
        ...
```

We **must** implement `insert_cable()`. Everything else is a convenience.

### The three callbacks

| Callback | Signature | What it does |
| --- | --- | --- |
| `get_observation()` | `() -> Observation` | Returns the most recent Observation (cameras + F/T + joints + controller state) |
| `move_robot(motion_update=None, joint_motion_update=None)` | XOR of the two | Publishes to the controller, switching modes if needed |
| `send_feedback(msg: str)` | `(str) -> None` | Publishes a string feedback message on the `/insert_cable` action |

### `set_pose_target` — the easiest way to move

```python
from geometry_msgs.msg import Pose, Point, Quaternion

target = Pose(
    position=Point(x=0.4, y=0.0, z=0.5),
    orientation=Quaternion(x=0.7071, y=0.7071, z=0.0, w=0.0),
)
self.set_pose_target(move_robot, target, frame_id="base_link")
```

Defaults: stiffness 90/90/90/50/50/50, damping 50/50/50/20/20/20, ff wrench 0, wrench feedback gains `[0.5, 0.5, 0.5, 0, 0, 0]`, MODE_POSITION.

## How the node loads our class

`aic_model.py:62-79` dynamically imports the module passed in the `policy` parameter:

```python
policy_module = importlib.import_module(self.policy_param)        # e.g. "aic_example_policies.ros.WaveArm"
# Then finds the class whose name matches the module suffix ("WaveArm")
policy_class = getattr(policy_module, suffix)
self.policy = policy_class(self)
```

So **module name must equal class name** (case sensitive). For our team policy, e.g. `team_autoencoder.AePolicy` means a file `team_autoencoder/AePolicy.py` containing `class AePolicy(Policy)`.

## Running it

```bash
ros2 run aic_model aic_model --ros-args \
  -p use_sim_time:=true \
  -p policy:=<dotted.module.path>
```

`use_sim_time:=true` is **essential**. Skip it and the clock will not match Gazebo's sim time and our deadlines will be wrong.

## Lifecycle flow

| State | Wrapper does | Our class does |
| --- | --- | --- |
| `unconfigured` | (default) | (idle) |
| → `configure` | calls `self.policy = PolicyClass(self)` | our `__init__` runs |
| `configured` | (idle) | (idle) |
| → `activate` | sets `is_active=True` | nothing |
| `active` | accepts `/insert_cable` goals → calls our `insert_cable()` in a thread | does the task |
| → `deactivate` | sets `is_active=False`; future goals rejected | finish current goal, then idle |
| → `cleanup` | destroys our policy instance | gone |
| → `shutdown` | destroys pubs/subs | gone |

See [`01_lifecycle_contract.md`](./01_lifecycle_contract.md) for transition timeouts.

## Common pattern

```python
import numpy as np
from aic_model.policy import Policy
from aic_control_interfaces.msg import MotionUpdate, TrajectoryGenerationMode
from geometry_msgs.msg import Pose, Point, Quaternion, Wrench, Vector3
from std_msgs.msg import Header

class AePolicy(Policy):
    def __init__(self, parent_node):
        super().__init__(parent_node)
        # LIGHT init only — no torch.load, no big files

    def insert_cable(self, task, get_observation, move_robot, send_feedback):
        # heavy imports go here
        import torch
        model = self._lazy_load_model()
        send_feedback(f"starting task {task.id} for {task.port_name}")

        deadline = self.time_now().nanoseconds + int(task.time_limit * 1e9)
        while self.time_now().nanoseconds < deadline:
            obs = get_observation()
            action = model.act(obs)
            self.set_pose_target(move_robot, action.pose)
            self.sleep_for(0.05)
            if self._converged(obs):
                send_feedback("inserted")
                return True
        return False
```

See [`03_writing_a_policy.md`](./03_writing_a_policy.md) for the full recipe.
