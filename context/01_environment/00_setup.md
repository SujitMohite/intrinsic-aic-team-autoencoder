# Local Setup

Source: [`docs/getting_started.md`](../../docs/getting_started.md).

## Minimum host

- Ubuntu 24.04
- 4–8 CPU cores, 32 GB+ RAM
- NVIDIA RTX 2070+ (8 GB VRAM minimum)
- ~30 GB free disk (container + assets + results)

Eval cloud node (for reference, our scores come from this):
- 64 vCPU, 256 GiB RAM, 1× NVIDIA L4 (24 GiB), CUDA 13.0, driver 580.126.09.

## One-time installs

1. **Docker Engine** + post-install (non-root). <https://docs.docker.com/engine/install/>
2. **NVIDIA Container Toolkit** (only if you have an NVIDIA GPU):
   ```bash
   sudo nvidia-ctk runtime configure --runtime=docker
   sudo systemctl restart docker
   ```
3. **Distrobox** (`sudo apt install distrobox` on Ubuntu).
4. **Pixi** — **pinned to 0.67.2** (newer hash format breaks the locked image):
   ```bash
   curl -fsSL https://pixi.sh/install.sh | sh
   pixi self-update --version 0.67.2
   ```

## Repo setup

```bash
mkdir -p ~/ws_aic/src
cd ~/ws_aic/src
git clone <our team fork>          # we are already in intrinsic-aic-team-autoencoder/
cd ~/ws_aic/src/intrinsic-aic-team-autoencoder
pixi install     # downloads ROS Kilted + lerobot + mujoco + etc.
```

Result: a `.pixi/` directory next to `pixi.toml`. Activation script `pixi_env_setup.sh` is auto-run and sets:
- `RMW_IMPLEMENTATION=rmw_zenoh_cpp`
- `ZENOH_CONFIG_OVERRIDE=transport/shared_memory/enabled=false`

## Eval container (the simulator)

```bash
export DBX_CONTAINER_MANAGER=docker
docker pull ghcr.io/intrinsic-dev/aic/aic_eval:latest
distrobox create -r --nvidia -i ghcr.io/intrinsic-dev/aic/aic_eval:latest aic_eval   # drop --nvidia for CPU-only
distrobox enter -r aic_eval
# inside the container:
/entrypoint.sh ground_truth:=false start_aic_engine:=true
```

This brings up:
- Gazebo (simulation window)
- RViz (visualization)
- `aic_bringup aic_gz_bringup.launch.py` with the AIC engine
- Zenoh router on `tcp/[::]:7447`
- A UR5e + Hand-E waiting at the home pose

The engine logs `No node with name 'aic_model' found. Retrying...` until we launch our policy.

## Run a baseline against it (Terminal 2, host side)

```bash
cd ~/ws_aic/src/intrinsic-aic-team-autoencoder
pixi run ros2 run aic_model aic_model --ros-args \
  -p use_sim_time:=true \
  -p policy:=aic_example_policies.ros.WaveArm
```

The `pixi run ros2 run` invocation does **not** need to be inside distrobox — pixi provides its own ROS environment and the Zenoh router bridges the two.

After the engine sees our node, it spawns the task board and cable and runs **3 trials** automatically.

## Verifying it worked

- Gazebo window shows task board + cable in gripper.
- Eval terminal logs `Trial 1/3`, `Trial 2/3`, `Trial 3/3` with scores.
- `~/aic_results/scoring.yaml` exists.

## Common first-time issues

| Symptom | Fix |
| --- | --- |
| `Error: no such container aic_eval` | `export DBX_CONTAINER_MANAGER=docker` (default is podman) |
| Low RTF in Gazebo | Wrong GPU — `sudo prime-select nvidia`, log out / in |
| `docker pull` fails | `gh auth login` to GHCR with a PAT |
| Pixi reinstall doesn't seem to update | `pixi reinstall <pkg>` — pixi doesn't auto-track local edits |
| `Discovery timeout` on aic_model | Heavy import at module top level — see [`../03_policy/04_pitfalls.md`](../03_policy/04_pitfalls.md) |

See [`../08_reference/01_troubleshooting.md`](../08_reference/01_troubleshooting.md) for more.

## NVIDIA RTX 50xx caveat

`lerobot` pins an older PyTorch that doesn't support `sm_120`. If on RTX 5090, add to `pixi.toml`:
```toml
[pypi-options.dependency-overrides]
torch = ">=2.7.1"
torchvision = ">=0.22.1"
```
