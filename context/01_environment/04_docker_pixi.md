# Docker + Pixi — Mental Model

Two parallel package universes coexist in this project. Knowing which is which saves hours.

## The two universes

| Layer | What lives there | When you use it |
| --- | --- | --- |
| **`aic_eval` Docker container** | Pre-built ROS 2 workspace including Gazebo + engine + controller + simulation assets | Always running on Terminal A as the simulator |
| **Pixi env on host** | Our editable workspace (Policy code, custom packages) + LeRobot/PyTorch/etc. | Always running on Terminal B as the policy |

These two universes talk to each other over a **Zenoh router** (port 7447) started by the eval container's entrypoint.

## Why this split

- Eval is **frozen** — the eval image is exactly what runs on the cloud during scoring. Don't modify it. Rebuilding from source is documented in `docs/build_eval.md` but rarely needed.
- Our policy needs **iterability** — Pixi makes it easy to add Python deps, swap PyTorch versions, etc., without touching the simulator side.

## Pixi quick reference

| Need | Command |
| --- | --- |
| Install / sync all deps | `pixi install` (slow — only on first clone or major change) |
| Reinstall one package after editing it | `pixi reinstall ros-kilted-aic-model` |
| Run a command in env | `pixi run <cmd>` |
| Open a shell in env | `pixi shell` |
| Add a ROS pkg | `pixi add ros-kilted-<pkg>` (from `robostack-kilted` channel) |
| Add a Python pkg | `pixi add --pypi <pkg>` |
| Pinned pixi version | **0.67.2** (see `docker/aic_model/Dockerfile:4`) |

Pixi prefixes ROS packages with `ros-kilted-` and converts `_` → `-` (`aic_example_policies` → `ros-kilted-aic-example-policies`).

## Local dependencies in pixi

If our policy package depends on, say, `aic_model_interfaces`, declare it in **both** the package's `pixi.toml` and the root `pixi.toml`. See `docs/policy.md:99-135` for the recipe.

## Docker layout

```
docker/
├── aic_eval/Dockerfile         # base: ros:kilted-ros-base; ships ws_aic install
├── aic_model/Dockerfile        # base: ros:kilted-ros-core; copies our policy + pixi; this is our submission template
├── rmw_zenohd/Dockerfile       # base: ros:kilted-ros-base; just the Zenoh router
└── docker-compose.yaml         # ties eval + model + zenohd together for local verification
```

`docker-compose.yaml` is the **local verification harness**: `docker compose -f docker/docker-compose.yaml up` will run the eval and our model side by side, exactly like the cloud will.

## Zenoh — discovery & ACLs

- Eval container starts a Zenoh **router** on `tcp/[::]:7447`.
- Model container starts a Zenoh **peer** that connects via `AIC_ROUTER_ADDR`.
- Both default to shared-memory disabled (`transport/shared_memory/enabled=false`).
- ACL can be enabled via `AIC_ENABLE_ACL=true` + `AIC_EVAL_PASSWD` + `AIC_MODEL_PASSWD`. The cloud eval enforces ACLs; **our policy will not be able to subscribe to forbidden topics** even if we try.

## Filesystem mounts vs build

- The aic_eval distrobox **mounts your home directory**, so `~/aic_results` is shared between the host and container.
- A `pixi run` invocation from the host writes results to the host's `~/aic_results` too.

## Submission Dockerfile flow

Our submission Dockerfile (modified copy of `docker/aic_model/Dockerfile`):

1. From `ros:kilted-ros-core`.
2. Install pixi 0.67.2.
3. `COPY` our policy package + interfaces + `pixi.toml`/`pixi.lock` into `/ws_aic/src/aic/`.
4. `RUN pixi install --locked` (the lockfile guarantees identical deps on the cloud).
5. Entrypoint script:
   - sets `RMW_IMPLEMENTATION=rmw_zenoh_cpp`
   - reads `AIC_ROUTER_ADDR` (provided by eval orchestration)
   - optionally reads passwords for ACL
   - `exec pixi run --as-is ros2 run aic_model aic_model "$@"`
6. `CMD` provides the policy parameter: `-p policy:=<our.module.Class> -p use_sim_time:=true`.

See [`../06_submission/00_packaging.md`](../06_submission/00_packaging.md) for the concrete recipe.
