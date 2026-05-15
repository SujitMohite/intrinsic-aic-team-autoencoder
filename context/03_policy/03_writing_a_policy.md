# Writing a Policy — Recipe

Source: [`docs/policy.md`](../../docs/policy.md) §Tutorial.

This is the concrete step-by-step for adding a new policy package to our workspace. Use it when bootstrapping `team_autoencoder` or any successor.

## 0. Decide where the code lives

Two options:

| Approach | When |
| --- | --- |
| Put the class in `aic_model/aic_model/MyPolicy.py` and point `-p policy:=aic_model.MyPolicy` | Smallest churn — no new package |
| Create our own package `team_autoencoder/` next to `aic_model/` | We need extra deps (torch, our own configs); cleaner for submission |

For the autoencoder approach, we go with **our own package** (`team_autoencoder/`).

## 1. Create the ROS package

```bash
pixi shell
ros2 pkg create team_autoencoder --build-type ament_python
```

## 2. Add dependencies

`team_autoencoder/package.xml`:
```xml
<depend>aic_control_interfaces</depend>
<depend>aic_model</depend>
<depend>aic_model_interfaces</depend>
<depend>aic_task_interfaces</depend>
<depend>geometry_msgs</depend>
<depend>rclpy</depend>
<depend>sensor_msgs</depend>
<depend>std_srvs</depend>
<depend>trajectory_msgs</depend>
```

## 3. Pixi packaging

`team_autoencoder/pixi.toml`:
```toml
[package.build.backend]
name = "pixi-build-ros"
version = "==0.3.3.20260113.c8b6a54"
channels = [
  "https://prefix.dev/pixi-build-backends",
  "robostack-kilted",
  "conda-forge",
]

[package.host-dependencies]
ros-kilted-aic-control-interfaces = { path = "../aic_interfaces/aic_control_interfaces" }
ros-kilted-aic-model              = { path = "../aic_model" }
ros-kilted-aic-model-interfaces   = { path = "../aic_interfaces/aic_model_interfaces" }
ros-kilted-aic-task-interfaces    = { path = "../aic_interfaces/aic_task_interfaces" }

[package.build-dependencies]
ros-kilted-aic-control-interfaces = { path = "../aic_interfaces/aic_control_interfaces" }
ros-kilted-aic-model              = { path = "../aic_model" }
ros-kilted-aic-model-interfaces   = { path = "../aic_interfaces/aic_model_interfaces" }
ros-kilted-aic-task-interfaces    = { path = "../aic_interfaces/aic_task_interfaces" }
```

Then in the **root** `pixi.toml`, under `[dependencies]`:
```toml
ros-kilted-team-autoencoder = { path = "team_autoencoder" }
```

Add any ML deps via:
```bash
pixi add --pypi torch torchvision
```

## 4. Write the policy class

`team_autoencoder/team_autoencoder/AePolicy.py`:

```python
from aic_model.policy import Policy
from aic_control_interfaces.msg import MotionUpdate, TrajectoryGenerationMode
from geometry_msgs.msg import Pose, Point, Quaternion, Wrench, Vector3
from std_msgs.msg import Header
import numpy as np
from rclpy.duration import Duration


class AePolicy(Policy):
    def __init__(self, parent_node):
        super().__init__(parent_node)
        self._model = None  # lazy-loaded

    def _lazy_init(self):
        if self._model is not None:
            return
        import torch  # heavy import — keep here
        from team_autoencoder.model import AutoencoderPolicy
        self._model = AutoencoderPolicy.load_from_checkpoint("/checkpoints/ae_v1.ckpt")
        self._model.eval()

    def insert_cable(self, task, get_observation, move_robot, send_feedback):
        self._lazy_init()
        send_feedback(f"starting {task.id}: insert {task.plug_type} into {task.port_name}")

        # Bound by sim time
        deadline_ns = self.time_now().nanoseconds + int(task.time_limit * 1e9)
        rate_hz = 10.0
        dt = 1.0 / rate_hz

        while self.time_now().nanoseconds < deadline_ns:
            obs = get_observation()
            action = self._predict(obs, task)
            move_robot(motion_update=action)
            self.sleep_for(dt)
            if self._converged(obs):
                send_feedback("converged — holding")
                return True
        send_feedback("time limit reached")
        return False

    def _predict(self, obs, task):
        # ... encoder → latent → policy head → MotionUpdate ...
        return MotionUpdate(...)

    def _converged(self, obs):
        # ... check force / vision criterion ...
        return False
```

## 5. Build / install

```bash
pixi reinstall ros-kilted-team-autoencoder
```

Re-run after every edit. Pixi does **not** auto-track source changes.

## 6. Test against the eval container

```bash
# Terminal A
distrobox enter -r aic_eval -- /entrypoint.sh

# Terminal B
pixi run ros2 run aic_model aic_model --ros-args \
  -p use_sim_time:=true \
  -p policy:=team_autoencoder.AePolicy
```

The engine fires `/insert_cable`. Watch `~/aic_results/scoring.yaml`.

## 7. Iterate

- Add `send_feedback("...")` liberally — these go into the trial log.
- Use `ros2 topic echo /aic_controller/controller_state` from another terminal to watch TCP error live.
- Use `ros2 lifecycle get /aic_model` to confirm states.

## 8. Submit

See [`../06_submission/`](../06_submission/). Our submission Dockerfile must:
- `COPY team_autoencoder /ws_aic/src/aic/team_autoencoder`
- `COPY` any model checkpoint files into the image
- `CMD ["--ros-args", "-p", "policy:=team_autoencoder.AePolicy", "-p", "use_sim_time:=true"]`

## Anti-patterns (will silently fail)

See [`04_pitfalls.md`](./04_pitfalls.md).
