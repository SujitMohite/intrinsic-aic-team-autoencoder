# Troubleshooting

Source: [`docs/troubleshooting.md`](../../docs/troubleshooting.md) plus our own experience (add here as we hit new failures).

## Gazebo / Sim

### Low real-time factor

If RTF stays well below 1.0, the engine still measures `task.time_limit` in sim seconds — we have more wall time, but our control rate is also slowed.

| Cause | Fix |
| --- | --- |
| Wrong GPU selected (integrated) | `sudo prime-select nvidia` + log out / in. Verify with `glxinfo -B`. |
| No GPU | Edit `aic_description/world/aic.sdf` and set `<enabled>false</enabled>` for the global-illumination plugin (two places). Visual policies will see flatter scenes. |
| Heavy other GPU workload | `nvidia-smi` to identify. Suspend the other workload. |

### Gazebo can't move robot

Likely in collision but not visibly touching. Right-click the suspect object → View → Collisions to inspect the collision mesh.

### Robot snaps oddly after a stall

The controller probably reset the target due to accumulated tracking error. Send a fresh `MotionUpdate` with a near-current TCP pose, then continue.

## Distrobox / Docker

### `Error: no such container aic_eval`

`export DBX_CONTAINER_MANAGER=docker` before `distrobox enter`. (Default is podman.)

### `docker pull` fails on GHCR

Authenticate with a GitHub PAT: `echo $GH_PAT | docker login ghcr.io -u <user> --password-stdin`.

### `docker compose up` works, but cloud Failed

Common: heavy imports at module top in our policy. See [`../03_policy/04_pitfalls.md`](../03_policy/04_pitfalls.md) §1.

## Zenoh

### `WARN Watchdog Validator … error setting scheduling priority`

Harmless. Zenoh's watchdog wanted higher OS priority and was denied. The system still works.

### Policy can't see topics

Most often: missing `RMW_IMPLEMENTATION=rmw_zenoh_cpp` in our shell. `pixi shell` sets it; outside pixi we must `export` it. Check `ros2 doctor` for middleware mismatch.

### "subscriber count is 0" for a topic we expect

Either:
- Zenoh router (eval container's `rmw_zenohd`) isn't running.
- Our pixi env disagrees with the router's ACL.

## Pixi

### Reinstall didn't pick up source edits

`pixi reinstall <pkg>` — and rerun. Pixi caches aggressively.

### `pixi install` hangs / fails

- Network — try again later or use a VPN.
- Lockfile drift — never edit `pixi.lock` by hand; let pixi regenerate it via `pixi update <pkg>`.

### Pixi version mismatch with Dockerfile

Dockerfile pins `0.67.2`. Locally:
```bash
pixi self-update --version 0.67.2
```

## PyTorch / NVIDIA

### RTX 50-series unsupported (sm_120)

Lerobot pins an old torch. Override in `pixi.toml`:
```toml
[pypi-options.dependency-overrides]
torch = ">=2.7.1"
torchvision = ">=0.22.1"
```

### CUDA out of memory in policy

Wrist-camera inference fits easily on L4. If OOM:
- Lower input resolution.
- Use FP16 inference.
- Check we're not double-loading the model on cancel/restart.

## Policy

### Engine logs "No node with name 'aic_model' found"

Our policy node isn't visible yet:
- `ros2 node list` confirms (run inside `pixi shell`).
- If absent, check that `pixi run ros2 run aic_model aic_model` actually started.
- If present but still not seen by the engine: Zenoh ACL or RMW mismatch.

### Engine logs "discovery timeout"

We took > 30 s to start. Move heavy imports inside `insert_cable`. See pitfalls.

### `scoring.yaml` exists but `tier_1.validity=0`

Tier 1 failed. Most common causes:
- Published commands in `unconfigured` / `configured` (e.g. a publisher that auto-publishes on construction).
- Lifecycle transition timeout exceeded.
- No motion commands emitted during the trial.

### Tier 3 always 0, no proximity reward

We're not converging on the port. Validate:
- Camera images are non-empty (`obs.left_image.height > 0`).
- Our motion commands have a valid `header.stamp` in sim time.
- We're not stuck in a `change_target_mode` mismatch (publish on the wrong topic).

## Submission portal

### Tag rejected

ECR tags are immutable; pick a new tag.

### `denied: requested access … is denied`

Wrong AWS profile, or our team URI typo. `aws sts get-caller-identity` to confirm.

### Status stays "Queued" > 30 min

Likely a cluster backlog. Don't resubmit; that wastes our quota. Refresh the page.

## When stumped

1. Reproduce with **CheatCode** as a control (it's deterministic-ish with `ground_truth:=true`). If CheatCode also breaks, env is broken — not our policy.
2. Diff the failing run's environment against a known-good run (`pixi tree`, `pip freeze`, Docker image SHA).
3. Capture a `ros2 bag` of the run for offline analysis.
4. Add a new entry to this file when we figure it out.
