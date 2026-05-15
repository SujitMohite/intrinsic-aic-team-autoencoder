# 24-Hour Multi-Machine Strategy

> **Honest top-30 probability with this plan: ~37%.** Best case 42%, worst case 18%. Top-50 ~58%. Valid submission ~88%.
> **Median improvement over single-machine plan: +12 percentage points.**

Companions: [`./01_data_24h.md`](./01_data_24h.md), [`./02_methods_24h.md`](./02_methods_24h.md). Long-form refs in [`../09_methods/`](../09_methods/) and [`../10_data/`](../10_data/).

## TL;DR

Three machines, no LAN, USB-only sync. **Desktop** (Ubuntu install + heavy training + authoritative eval). **Laptop 2 (8 GB 4070)** dedicated to parallel ACT training — *not* data collection — because at our data scale (1500-2000 demos ceiling) **the gain from more training configs (8 instead of 3-4) exceeds the gain from more demos**. **Laptop 1 (T1000 4 GB)** runs continuous headless Gazebo data collection from hour 0 — it's free GPU-time with no contention against training. The Codex orchestrator is *not* coordinated across machines; we use a pre-split shortlist where each machine knows its lane. Two USB syncs (hours 6 and 14) hand fresh demos to Desktop + Laptop 2. Submit the winner of 8 trained variants + classical fallback at hour 22.

## Confirmed inputs

| Item | Status |
|---|---|
| Both laptops have Ubuntu 24.04 + pixi 0.67.2 + aic_eval Docker image | ✓ ready |
| Desktop OS install time | ~2 hours (user estimate, "I am fast") |
| Laptop 2 VRAM | 8 GB confirmed |
| Cross-machine network | None — USB drive only |
| User available throughout 24h | Assumed |

## Per-machine role allocation (and why)

### Desktop (Xeon, RTX 2000 Ada 16 GB, sm_89) — primary training + authoritative eval

After Phase 0 install completes, Desktop is the workhorse:
- 16 GB VRAM fits the full ACT shortlist at batch 32.
- **sm_89 matches the eval cloud's L4** — what trains here transfers exactly to eval.
- Authoritative eval node (we trust Desktop's `scoring.yaml` over Laptop 2's, since architectures match).
- 4 training cycles × ~4 h each in hours 2-22 = 4 trained variants.

### Laptop 2 (i7-13700HX, RTX 4070 mobile 8 GB) — parallel ACT training only

- 8 GB caps us to ACT-family configs at batch 16 (Diffusion Policy variants won't fit cleanly).
- **Not** data collection — see critical-analysis section below for why this allocation.
- 4 training cycles × ~4 h each in hours 2-22 = 4 trained variants.
- Runs the **same shortlist as Desktop** but with the 8 GB-fitting subset (frozen DINOv2-S + ACT, no diffusion).

### Laptop 1 (i7-10875H, T1000 4 GB) — continuous headless Gazebo data collection + dev box

- 4 GB VRAM is below AIC minimum spec for GUI Gazebo, but **fine for headless with GI off + 256×256 cameras** (~3 GB VRAM used).
- **Continuous collection from hour 0 to hour 22** = 22 hours of background work that costs us nothing in GPU-training time.
- Throughput estimate: 25-35 ep/h sustained (slower than ideal due to T1000 + thermal throttling under sustained load).
- Total contribution: **600-770 episodes** over 22 hours. Significant.
- Doubles as the dev box: code editing, USB image preparation, Codex prompt orchestration, monitoring.

## Critical analysis: data vs. training runs allocation

The non-obvious question is what Laptop 2 does. Two extremes:

| Allocation | Data total | Training runs | Estimated impact |
|---|---|---|---|
| **All-on-data** (L2 collects all 20h) | ~2400 episodes | 4 (Desktop only) | +85% data → roughly +15-20% policy performance (log-scaling at this regime) |
| **All-on-training** (L2 trains 4 cycles) | ~1300 episodes | **8** (4 Desktop + 4 L2) | 2× config search → roughly +20-25% policy performance (high hyperparameter sensitivity in IL) |
| Hybrid (L2 splits 50/50) | ~1700 episodes | 6 | +10-15% |

**Pick all-on-training.** Reasoning:
- ACT/F/T-ACT performance at our scale follows roughly `score ∝ log(demos)` in the 500-3000 range. Going from 1300 → 2400 demos = +85% data, only +15-20% expected gain.
- ACT performance is **highly hyperparameter-sensitive**. Best vs worst config in our 7-config shortlist could differ by 20-30%. Testing more configs has higher expected variance reduction.
- The published evidence in the IL agent's report supports this: methods that "work" are 60-90% successful; methods with wrong hyperparams are 5-15%. The gradient on hyperparams is steeper than the gradient on data quantity.

**Counter-argument** (your earlier "simple scales" intuition): more data is the bitter-lesson play. **Where it would beat hyperparameter search**: at 100×+ data scale. Not here.

This is the kind of micro-decision that auto-research could discover empirically over weeks. In 24h, we commit based on the prior.

## The 3-phase timeline

### Phase 0 — Setup (hours 0-2)

User personally: install Ubuntu 24.04 + nvidia-driver-580 + Docker + NVIDIA Container Toolkit + pixi 0.67.2 + distrobox + pull `ghcr.io/intrinsic-dev/aic/aic_eval:latest` on Desktop. ~2 hours.

In parallel (no human time required after kickoff):
- **Laptop 2**: Codex builds `train_policy.py` (LeRobot ACT wrapper with our obs schema), `eval_harness.sh` (headless Gazebo + scoring.yaml summarizer), pre-downloads `facebook/dinov2-small` weights to local cache, validates 5-min smoke train.
- **Laptop 1**: Codex builds the orchestrator script (`pipeline/orchestrator.py`), tests headless Gazebo with GI off, starts an initial data trickle (~30 episodes during Phase 0 just to stress-test the pipeline).

By end of hour 2: Desktop online, training script tested on Laptop 2, ~30-50 episodes already on disk.

### Phase 1 — Productive (hours 2-22)

**Hour 2:00 - 2:30 — Sync 0**: USB hop from Laptop 2 → Desktop. Carries: `train_policy.py`, `eval_harness.sh`, `pixi.lock`, ~30 demos. Desktop runs a 10-minute smoke train + 5-trial eval. **If smoke fails: triage. Don't proceed to long runs with a broken pipeline.**

**Hour 2:30 - 6:30 — Round 1** (~4 hours, 1st training cycle):
- Desktop: train **v1** = ACT + F/T concat + frozen DINOv2-S + medium DR + chunk 16, on whatever demos exist (~50-150).
- Laptop 2: train **v2** = same as v1 but chunk 8 (ablation on chunk size).
- Laptop 1: continuous data collection. Adds ~120 episodes during this cycle.

**Hour 6:30 - 7:30 — Sync 1**: USB hop. Carries: ~150 new demos from Laptop 1 → Desktop and Laptop 2 (both copies). Desktop runs **eval on v1**. Laptop 2 runs **eval on v2** (Desktop's eval is authoritative; Laptop 2's is a cross-check). Codex (running on Laptop 1) reads results, picks v3 and v4 from the shortlist.

**Hour 7:30 - 11:30 — Round 2** (~4 hours, 2nd training cycle):
- Desktop: train **v3** = best v1/v2 config + aggressive DR.
- Laptop 2: train **v4** = best v1/v2 config + ResNet-18 trained encoder instead of DINOv2-S (encoder ablation).
- Laptop 1: continuous collection. Demo total reaching ~500.

**Hour 11:30 - 12:00 — Sync 2**: USB hop, evals, Codex picks v5/v6.

**Hour 12:00 - 16:00 — Round 3** (~4 hours, 3rd training cycle):
- Desktop: train **v5** = best so far + extended epochs on ~700-800 demos.
- Laptop 2: train **v6** = best so far without F/T (this is the **F/T ablation** — confirms F/T is helping).
- Laptop 1: continuous collection. Demo total reaching ~900.

**Hour 16:00 - 16:30 — Sync 3**: USB hop, evals, pick winner trajectory + final variant.

**Hour 16:30 - 20:30 — Round 4** (~4 hours, final training cycle):
- Desktop: train **v7** = best hyperparameters discovered, longest training schedule, full data (~1200-1500 demos at this point).
- Laptop 2: train **v8** = sister of v7 with different random seed (variance check) OR v7-with-more-DR if seed variance not interesting.
- Laptop 1: collects to the bitter end. Final demo count: 1300-1700.

**Hour 20:30 - 21:30 — Final eval**: 30-trial regression set on Desktop for v7, v8, and the classical fallback (built side-task per [`./02_methods_24h.md`](./02_methods_24h.md) §Fallback). Compare against authoritative metric.

**Hour 21:30 - 22:00 — Pick winner**: Best of {v1..v8} or classical fallback.

### Phase 2 — Submit (hours 22-24)

**Hour 22:00 - 23:30 — Container build** on Desktop:
- Build `docker/team_autoencoder/Dockerfile`.
- Run `docker compose -f docker/docker-compose.yaml build model`.
- Run `docker compose up` locally for end-to-end sanity check (1 full 3-trial run).

**Hour 23:30 - 24:00**: AWS auth, ECR push, portal submission. Buffer.

## Codex orchestration across no-LAN machines

We deliberately **do not** build cross-machine coordination. Two reasons:
1. USB-only sync means we can't have shared state in real time.
2. The shortlist is small enough that human-readable assignment beats automated scheduling.

What we use instead:

### Pre-split shortlist (committed at hour 0)

```yaml
# shortlist.yaml — copied to both Desktop and Laptop 2 at Sync 0

desktop_lane:
  v1: {chunk: 16, ft: true, encoder: dinov2-s, dr: medium}
  v3: {chunk: 16, ft: true, encoder: dinov2-s, dr: aggressive}     # adapt after v1 results
  v5: {chunk: ?,  ft: true, encoder: ?, dr: ?, extended_epochs: true}  # filled at Sync 2
  v7: {best_yet, extended_epochs: true, full_data: true}            # filled at Sync 3

laptop2_lane:
  v2: {chunk: 8, ft: true, encoder: dinov2-s, dr: medium}
  v4: {chunk: 16, ft: true, encoder: resnet18-trained, dr: medium}
  v6: {chunk: 16, ft: false, encoder: dinov2-s, dr: medium}        # F/T ablation
  v8: {seed: 2 or +DR, same as v7}
```

### Per-machine Codex agent

Each machine runs an independent Codex agent reading its lane. The agent:
1. At training start: writes config to disk, runs `train_policy.py`, logs.
2. At training end: runs `eval_harness.sh`, logs metric.
3. At sync point: human carries USB → next config is filled in by human reading prior results.

**The human is the orchestrator**, Codex is the executor. At each of 3-4 sync points the human looks at the metrics so far and decides what each machine trains next. This takes ~10 minutes per sync. Total operator time: 30-40 min across 24h.

### What goes on the USB drive each sync

| Sync | Direction | Contents | Time |
|---|---|---|---|
| Sync 0 (h 2:00) | Laptop 2 → Desktop | train_policy.py, eval_harness.sh, pixi.lock, shortlist.yaml, ~30 demos | 5-10 min |
| Sync 1 (h 6:30) | Laptop 1 → Desktop + Laptop 2 | ~150 new demos, v1 + v2 eval results | 10-15 min |
| Sync 2 (h 11:30) | Laptop 1 → Desktop + Laptop 2 | ~350 cumulative demos, v3 + v4 results, updated shortlist for v5/v6 | 10-15 min |
| Sync 3 (h 16:00) | Laptop 1 → Desktop + Laptop 2 | ~700 cumulative, v5 + v6 results, locked v7/v8 spec | 10-15 min |
| Sync 4 (h 20:30) | Desktop → Submission staging | final winning checkpoint | 5 min |

USB 3.0 at ~120 MB/s for ~50 GB cumulative demos: each sync transfers maybe ~5-10 GB of new data, ~1-2 min actual transfer. The overhead is mounting + verifying.

## Updated training shortlist (8 configs, all fit 8 GB)

All configs share: ACT base, frozen DINOv2-S encoder (unless varied), task one-hot conditioning, RTC at inference.

| # | Lane | Chunk | F/T | Encoder | DR | Note |
|---|---|---|---|---|---|---|
| v1 | Desktop | 16 | ✓ | DINOv2-S | medium | Baseline. The expected winner. |
| v2 | Laptop 2 | 8 | ✓ | DINOv2-S | medium | Chunk-size ablation. |
| v3 | Desktop | 16 | ✓ | DINOv2-S | aggressive | DR ablation. |
| v4 | Laptop 2 | 16 | ✓ | ResNet-18 (trained) | medium | Encoder ablation (DINOv2 vs trained ResNet). |
| v5 | Desktop | 16 | ✓ | best | best | Best v1-v4 + extended epochs. |
| v6 | Laptop 2 | 16 | ✗ | DINOv2-S | medium | **F/T ablation — proves F/T is helping.** |
| v7 | Desktop | 16 | ✓ | best | best | Full data + extended epochs. Final. |
| v8 | Laptop 2 | 16 | ✓ | best | best | Sister of v7 with different seed OR slightly more DR. |

**Diffusion Policy is OUT** of the shortlist for 24h — won't fit 8 GB at usable batch, and we want both GPUs running the same family. In 48h plan: add a Desktop-only Diffusion variant.

## Failure modes and fallback paths

| Failure | Probability | Detection | Mitigation |
|---|---|---|---|
| Desktop Ubuntu install takes > 4 h | Medium | Wall clock at hour 4 | At hour 4, if not done: shift to laptop-only path. Top-30 odds drop to ~22%. Laptop 2 takes over primary training role. |
| Desktop driver fails (sm_89 Ada on Ubuntu 24.04 driver mismatch) | Low-medium | `nvidia-smi` doesn't see GPU | Try driver versions 580 / 575 / 570. Budget 1 hour. If still failing by hour 4: laptop-only path. |
| `aic_eval` Docker pull fails on Desktop | Low | `docker pull` errors | `docker save` it on Laptop 2, transfer via USB, `docker load` on Desktop. |
| Laptop 2 OOM on ACT at batch 16 | Low | Training script errors | Drop batch to 8. Slight training-time hit. |
| USB drive corrupts | Low (single drive); Medium across 24h | Mount errors | **Keep 2 USB drives in rotation.** Re-snapshot from source. |
| Laptop 1 thermal throttle drops RTF below 0.4 | Medium | RTF logging | Pause data collection for 15 min. External fan / elevated laptop. Sustained 25 ep/h instead of 35. |
| `train_policy.py` has a bug discovered at hour 4 | Medium-high | Eval shows nonsense | Eats ~2 hours fixing. The smoke-test at Sync 0 is meant to catch this *before* it eats Round 1. |
| Gazebo cable softlock | Medium | Per-trial timeout fires | Already handled by orchestrator. |
| Sync 0 smoke test fails | Low if Phase 0 was careful | Eval gives noise | Fix BEFORE Round 1. Don't proceed with broken plumbing. |
| Sync 2 reveals all v1-v4 plateaued at < 20 Tier 3 | Medium | Eval results | Pivot: ship classical fallback. Run a single final training cycle as a sanity check, but don't expect it to save us. |
| Container build fails at hour 22 | Medium | `docker build` errors | Budget includes 1.5 hours for build + push. Container build is well-trodden by Sync 0 testing. |

## Updated honest top-30 odds (vs prior plans)

| Plan | Conditions | Top-30 |
|---|---|---|
| Single-machine (`02_methods_24h.md`) | Desktop already installed, single GPU | ~25% |
| Two-laptop only (Desktop fails install) | Best case: Laptop 2 primary, no sm_89 match | ~22% |
| **Three-machine (this file)** | Desktop install ≤ 2 h; all 3 productive Phases 1-3 | **~37%** |
| Three-machine, all goes well | Best case: 8 trained variants, one clearly wins | ~42% |
| Three-machine, install fights us | Desktop online by hour 6 | ~28% |

**The median three-machine outcome (37%) is 12 percentage points better than single-machine (25%).** The gain comes mostly from:
- Testing 6-8 ACT variants instead of 3-4 (~+10pp).
- Free continuous data collection on Laptop 1 (~+2pp).
- Architecture parity with eval cloud preserved on Desktop (~unchanged).

## Where this plan can break and you should pause

Three checkpoints with explicit go/no-go:

1. **Hour 2:30 — Smoke test on Desktop**. If `train_policy.py` doesn't run end-to-end, do NOT proceed to Round 1. Fix or fall back to laptop-only.
2. **Hour 12:00 — Round 2 eval review**. If best of v1-v4 has Tier 3 < 15 across all NIC indices, the data or pipeline has a deeper problem. Either pivot to classical fallback immediately or spend Round 3 debugging instead of training.
3. **Hour 20:00 — Final pre-submit eval**. If our best Tier 3 mean < 25, **ship the classical fallback** (assuming it cleared Tier 1). It probably scores higher.

## What about the team-autoencoder?

Honest: **out of scope for 24h.** Frozen DINOv2-S beats from-scratch β-VAE at our data scale (see [`../09_methods/17_repr_autoencoder.md`](../09_methods/17_repr_autoencoder.md) §"My note"). The team-autoencoder identity is not abandoned — it's the right play at 48h+ when we have time to compete a from-scratch AE against DINOv2 head-to-head. For 24h, take the free win.

## What changes vs. `02_methods_24h.md`

| Aspect | Single-machine plan | This (multi-machine) plan |
|---|---|---|
| Training runs in 24h | 3-4 | **8** |
| Demos collected | 1500-2000 | 1300-1700 (less because L2 trains instead of collects) |
| Hyperparameter coverage | 3 shortlist configs | 7-8 of shortlist |
| F/T ablation tested | No (no budget) | **Yes (v6)** |
| Encoder ablation tested | No | **Yes (v4)** |
| Chunk-size ablation tested | No | **Yes (v2)** |
| Sister-seed variance estimate | No | **Yes (v8)** |
| Failure-mode coverage | 1 GPU = SPOF | 3-machine; graceful degradation |
| Top-30 odds | ~25% | **~37%** |

## What we'd add at 48 hours (for reference)

- Add Diffusion Policy as a Desktop-only third lane (16 GB needed; L2 can't run).
- Run Isaac Lab on Laptop 2 for cross-sim DR demos (the NVIDIA-prepared `aic_isaac` assets work without our SFP port — could still help with SC trial transfer).
- Two USB drives in flight at all times (eliminates sync wait).
- Manual teleop demo collection on Laptop 1 evenings for HIL-SERL fallback path.

## Cross-refs

- Companions: [[data-24h]] ([`./01_data_24h.md`](./01_data_24h.md)), [[methods-24h]] ([`./02_methods_24h.md`](./02_methods_24h.md)).
- Full method/data landscape: [`../09_methods/00_index.md`](../09_methods/00_index.md), [`../10_data/00_index.md`](../10_data/00_index.md).
- Long-form auto-research design: [[auto-research-loop]] ([`../10_data/12_auto_research_loop.md`](../10_data/12_auto_research_loop.md)).
- Hardware inventory: [[resources]] ([`../07_team/03_resources.md`](../07_team/03_resources.md)).
- Submission flow: [[packaging]] ([`../06_submission/00_packaging.md`](../06_submission/00_packaging.md)) + [[upload]] ([`../06_submission/01_upload.md`](../06_submission/01_upload.md)).
