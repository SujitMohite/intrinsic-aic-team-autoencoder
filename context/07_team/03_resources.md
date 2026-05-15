# Resources — Hardware & Budget

STATUS: accepted. Update when allocation changes.

## Hardware inventory

| Box | CPU | RAM | GPU | VRAM | Role |
| --- | --- | --- | --- | --- | --- |
| **Desktop** (primary) | Xeon, 32 cores | 64 GB ECC | NVIDIA RTX 2000 Ada (sm_89) | **16 GB** GDDR6 | Eval container, training, inference, submission build |
| **Laptop 1** | i7-10875H, 8 c / 16 t | 64 GB | NVIDIA Quadro T1000 Max-Q (sm_75) | **4 GB** | Code editing, Git, docs, SSH; **below AIC min** for sim/ML |
| **Laptop 2** | i7-13700HX | 32 GB | NVIDIA RTX 4070 mobile | ~8 GB | **Out of scope for this project** (team preference) |

## Architecture match to eval cloud

| Parameter | Eval cloud | Desktop | Match |
| --- | --- | --- | --- |
| GPU arch | NVIDIA L4 (Ada, sm_89) | RTX 2000 Ada (sm_89) | ✅ identical compute capability |
| VRAM | 24 GB | 16 GB | ⚠️ smaller; cap training batch / model size |
| CUDA | 13.0 | depends on driver | ⚠️ use PyTorch ≥ 2.7 to avoid `sm_120`-style locks; see [`08_reference/01_troubleshooting.md`](../08_reference/01_troubleshooting.md) |
| vCPU | 64 | 32 | ✅ fine |
| RAM | 256 GB | 64 GB ECC | ✅ enough for AIC |

**Implication:** trained checkpoints from desktop should run on L4 unmodified. Plan training to fit in **16 GB** at peak.

## Where each phase happens

| Phase | Where |
| --- | --- |
| Repo edits, Git, planning | Laptop 1 |
| Sim + Gazebo end-to-end | Desktop only |
| Pixi installs, ROS workspace | Desktop primary; Laptop 1 ok for non-sim package work |
| LeRobot / PyTorch training | Desktop only |
| Isaac Lab parallel envs | Desktop (cap ~256 envs at 16 GB) |
| MuJoCo CPU sweeps | Desktop primary; Laptop 1 ok (CPU-only) |
| Docker build of submission image | Desktop (CUDA wheels are big) |
| `docker compose up` verification | Desktop |
| ECR push | Either, network permitting |

## Single-point-of-failure risk

Excluding Laptop 2 makes the desktop the **only** box that can validate or train. Mitigations:

- Keep the desktop on UPS / stable power if possible.
- Push our datasets and checkpoints to a separate location (HF Hub private repo, or even a USB SSD) at least once per day.
- Tag-and-push a working submission image to ECR as a fallback before iterating further.

## AI tooling budget

| Tool | Budget | Best use |
| --- | --- | --- |
| **Codex** | unlimited | Boilerplate, scaffolding, tests, dataset loaders, Dockerfile edits, training scripts |
| **Claude Code (Opus 4.7, 1M ctx)** | **$550** | Architectural decisions, cross-file debugging, sim-to-sim transfer questions, deep code review, post-mortems on failed submissions |

**Heuristic:** Anything that's "what's the right approach here" or "trace this bug across N files" → Claude. Anything that's "write the boilerplate" or "do this repetitive transformation" → Codex.

**Budget protection:**
- Lean on cached file reads (the harness already caches `/CLAUDE.md` + open files into the prompt cache).
- Load **only the relevant `context/` files** for a question — don't dump the whole tree.
- Avoid long thinking blocks on trivial tasks; force-route those to Codex.

## Disk / network

- Eval image (`aic_eval`): ~10 GB.
- Pixi env: ~5–8 GB once installed.
- Submission image build: ~15–25 GB.
- Datasets (LeRobot demos for 50 episodes, 3 cams): ~5–20 GB.
- **Minimum free disk on Desktop: 150 GB recommended.**
- ECR push: a few GB per submission. Budget reasonable bandwidth at submission time.

## Action items

- [ ] Verify Desktop has Ubuntu 24.04 (AIC requirement).
- [ ] Verify `nvidia-smi` on Desktop reports the RTX 2000 Ada and a CUDA-13-compatible driver.
- [ ] `df -h /var/lib/docker` ≥ 150 GB free.
- [ ] Decide whether to keep Laptop 2 as a warm fallback (`pixi install` + Docker pull only, no code dev).
- [ ] Pre-stage a fallback submission image (e.g. a CheatCode-style policy that does **not** use `/scoring/tf`) on ECR before iterating on the AE policy.
