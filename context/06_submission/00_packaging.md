# Packaging — Building Our Submission Image

Source: [`docs/submission.md`](../../docs/submission.md), [`docker/aic_model/Dockerfile`](../../docker/aic_model/Dockerfile), [`docker/docker-compose.yaml`](../../docker/docker-compose.yaml).

## Two paths

### Path A — Reuse `docker/aic_model/Dockerfile` with a different policy

If our policy file lives inside `aic_model/aic_model/MyPolicy.py` and needs no extra deps:

1. Edit `docker/aic_model/Dockerfile` line ~60:
   ```dockerfile
   CMD ["--ros-args", "-p", "policy:=aic_model.MyPolicy", "-p", "use_sim_time:=true"]
   ```
2. Skip to [Building](#building).

### Path B — Our own package (`team_autoencoder/`)

Recommended. Cleaner submission, isolates deps.

```bash
mkdir -p docker/team_autoencoder
cp docker/aic_model/Dockerfile docker/team_autoencoder/Dockerfile
```

Edit `docker/team_autoencoder/Dockerfile`:

```dockerfile
FROM docker.io/library/ros:kilted-ros-core AS build

RUN apt update && apt install -y git && \
    curl -fsSL https://pixi.sh/install.sh | PIXI_VERSION=0.67.2 bash
ENV PATH="/root/.pixi/bin:$PATH"

# Base packages (unchanged)
COPY aic_example_policies /ws_aic/src/aic/aic_example_policies
COPY aic_model            /ws_aic/src/aic/aic_model
COPY aic_interfaces       /ws_aic/src/aic/aic_interfaces
COPY aic_utils            /ws_aic/src/aic/aic_utils
COPY pixi.toml pixi.lock  /ws_aic/src/aic/
COPY pixi_env_setup.sh    /ws_aic/src/aic/

# OUR additions
COPY team_autoencoder     /ws_aic/src/aic/team_autoencoder
# If we have a checkpoint baked in:
COPY checkpoints          /checkpoints

SHELL ["/bin/bash", "-c"]
RUN --mount=type=cache,target=/root/.cache/rattler/cache \
    --mount=type=cache,target=/ws_aic/src/aic/.pixi/build \
    cd /ws_aic/src/aic && pixi install --locked

WORKDIR /ws_aic/src/aic

# Reuse the same entrypoint (zenoh peer setup), just change CMD
COPY --chmod=755 <<"EOF" /entrypoint.sh
#!/bin/bash
set -e
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
if [[ -z "$AIC_ROUTER_ADDR" ]]; then
  echo "AIC_ROUTER_ADDR must be provided" >&2
  exit 1
fi
ZENOH_CONFIG_OVERRIDE='connect/endpoints=["tcp/'"$AIC_ROUTER_ADDR"'"]'
ZENOH_CONFIG_OVERRIDE+=';transport/shared_memory/enabled=false'
export ZENOH_CONFIG_OVERRIDE
exec pixi run --as-is ros2 run aic_model aic_model "$@"
EOF

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--ros-args", "-p", "policy:=team_autoencoder.AePolicy", "-p", "use_sim_time:=true"]
```

> Keep the **ACL conditional** from the upstream Dockerfile if we want to test with ACLs locally; the eval cloud may or may not require it depending on the phase.

## Update `docker/docker-compose.yaml`

Find the `model` service and point it at our Dockerfile:

```yaml
services:
  model:
    image: team-autoencoder:v1
    build:
      dockerfile: docker/team_autoencoder/Dockerfile
      context: ..
```

## Building

```bash
docker compose -f docker/docker-compose.yaml build model
```

The first build downloads pixi deps (~2–5 GB). Subsequent builds use BuildKit cache mounts and are fast.

## Local verification (CRITICAL)

```bash
docker compose -f docker/docker-compose.yaml up
```

This brings up:
- `aic_eval` container (running engine + sim)
- `rmw_zenohd` (router)
- Our `team-autoencoder:v1` container

Watch logs from all three. Confirm:
- Our model container reaches `active` lifecycle.
- All 3 trials run.
- A non-zero `scoring.yaml` is produced.

> **Don't push without this check.** Failed pulls on the portal count against our 1-per-day submission quota.

## What to keep OUT of the image

- Source datasets (parquet files, raw videos) — too large.
- HuggingFace cache directories.
- Build artifacts (`.pixi/build/`, `__pycache__/`) — pixi rebuilds inside the image anyway.
- `.git/` — strip via `.dockerignore`.

`.dockerignore` is already present at repo root; extend it for our package's transient files.

## What to keep IN

- `team_autoencoder/` source.
- The model checkpoint we want to use (typically a single `.pt` or `.safetensors` file under `checkpoints/`).
- Updated `pixi.toml` / `pixi.lock` reflecting any new dependencies (run `pixi install` locally first to refresh the lock).

## Size budget

Eval orchestration tolerates large images, but pull time eats into our scoring window:

| Tier | Size | Pull time on cloud |
| --- | --- | --- |
| Lean | < 5 GB | fast |
| Reasonable | 5–10 GB | ok |
| Heavy | 10–25 GB | slow but allowed |
| Bad | > 25 GB | reconsider — strip CUDA wheels, etc. |

## Sanity: what the image starts

```bash
docker run --rm -e AIC_ROUTER_ADDR=localhost:7447 team-autoencoder:v1 --help
```

Should print `ros2 run aic_model aic_model` help text after pixi bootstrap.

## Next

[`01_upload.md`](./01_upload.md) — pushing to ECR.
