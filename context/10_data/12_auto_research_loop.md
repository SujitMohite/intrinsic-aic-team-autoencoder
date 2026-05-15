# Karpathy-Style Autonomous Research Loop for AIC

STATUS: design document. To be instantiated as code in a later phase.

## TL;DR

A concrete, single-workstation, Codex-driven research loop tailored to AIC. **Inspired by Karpathy's `autoresearch` (March 2026)** which used a 3-file pattern — `prepare.py` (frozen eval harness), `train.py` (only file the agent edits), `program.md` (English research methodology) — to run >700 experiments in 48 hours and find ~20 stacking improvements on nanochat training. We adapt this pattern to AIC: frozen Gazebo eval harness, narrow editable training surface, propose-evaluate-archive outer loop driven by **Codex (unlimited) with Claude-Code occasional review** of failed branches.

This file is the **design specification**, not the implementation. The implementation is one of the **first concrete software builds** after we finish this research artifact.

## Why now

The user gave us:
- **Unlimited Codex budget.**
- **One desktop** (RTX 2000 Ada, 16 GB sm_89).
- **A scoring metric we can run automatically** (`scoring.yaml` from a Gazebo trial).
- **A keystone data pipeline plan** ([`./02_offline_scripted_groundtruth.md`](./02_offline_scripted_groundtruth.md)) that automates data generation.

That's exactly the substrate Karpathy describes for autoresearch. We should build it.

## The 5 elements that successful auto-research loops share

(synthesis of Eureka, DrEureka, AI Scientist v2, Karpathy autoresearch, AlphaEvolve, OpenAI Cookbook Codex loop):

1. **A frozen, narrow, numeric evaluator the agent cannot edit.**
2. **A small, well-scoped surface the agent may edit.**
3. **An archive of accepted variants** (git-based or DB-based).
4. **A propose-evaluate-archive evolutionary outer loop**, not LLM-as-judge in the inner loop.
5. **English methodology** (`program.md` style) + Python execution.

If any of these is missing, the loop reward-hacks. We design around all 5.

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│  program.md            (English research methodology)          │
│   ├─ what's in scope to edit                                   │
│   ├─ what's out of scope (never touch)                         │
│   ├─ what reward / metric to optimize                          │
│   ├─ revert criteria (any nan, any crash, > 2x training time)  │
│   └─ documented hypotheses (Diffusion vs ACT vs F/T concat)    │
└────────────────────────────────────────────────────────────────┘

┌──── Codex loop ────────────────────────────────────────────────┐
│  1. read program.md + last 20 git commits in archive           │
│  2. propose a patch to train.py / config.yaml                  │
│  3. apply patch in fresh worktree                              │
│  4. run train script (timeboxed)                               │
│  5. run frozen eval harness                                    │
│  6. read eval metric                                           │
│  7. commit → archive  OR  revert                               │
│  8. loop                                                       │
└────────────────────────────────────────────────────────────────┘

  ↓ once per week
┌──── Claude-Code reviewer (us, manual) ─────────────────────────┐
│  - read archive of last 50-200 experiments                     │
│  - write one-page "what we've learned + dead ends + next dir"  │
│  - update program.md if research strategy needs to change      │
└────────────────────────────────────────────────────────────────┘
```

## The frozen evaluator

A **single shell script** that takes:
- Path to a trained policy checkpoint.
- Path to an `aic_engine` config.
- A seed.

And outputs **one line of JSON**:
```json
{"total_score": 187.3, "tier_3_mean": 47.2, "valid": true, "trials": 3, "wall_clock_s": 312}
```

**Requirements**:
- Codex cannot read or edit the script. Place it in a directory outside of the agent's workdir.
- The script invokes headless Gazebo + the engine + the policy, reads `scoring.yaml`, summarizes.
- Crashes (nan, hang, RTF dropping below 0.3) → `{"valid": false}` with a small score (e.g. -1.0). Distinguishes from "experiment ran cleanly but produced 0 points."
- N seeds per evaluation (e.g. 5 seeds; report mean + std). Karpathy uses ~5 seeds to denoise.

## The editable surface

**Phase 1 (Karpathy-style narrow surface)**: one editable file `train_policy.py` + one editable `config.yaml`. The agent edits these; nothing else.

`train_policy.py` skeleton (the agent edits this):
```python
# train_policy.py — the only file the agent may edit.
# DO NOT IMPORT from data/, eval/, engine/, controllers/, anything outside this directory.
# DO NOT call subprocess to bypass the harness.

import lerobot
import torch

def train(config: dict) -> Path:  # returns path to checkpoint
    dataset = lerobot.load_dataset(config["dataset"])
    encoder = make_encoder(config)
    policy  = make_policy(config, encoder)
    optim   = make_optim(config, policy)
    for step in range(config["steps"]):
        batch = dataset.sample(config["batch"])
        loss = policy.loss(batch)
        optim.step()
        # ...
    return save_checkpoint(policy)
```

`config.yaml`:
```yaml
policy: act
encoder: resnet18
chunk_size: 16
batch: 32
lr: 1e-4
augmentation: light
ft_concat: true
dr_strength: 0.3
steps: 50000
```

**Phase 2 (after Phase 1 works)**: widen surface to allow a few more files (a custom encoder, a custom reward function).

## The archive

Git-based. Every Codex iteration:
- New worktree from `main`.
- Codex commits its patch.
- Eval runs.
- If metric improves vs `main`: PR-merge into `main`.
- If not: discard the worktree.

**Archive query**: the next iteration's Codex prompt includes the last N commits' diffs + their eval metrics. Codex sees "I tried chunk_size=32 → score dropped 5 pts" and learns from it.

**Failsafe**: a separate `experiments/` branch keeps the last 100 *non-merged* experiments too, with their metrics, for retrospective analysis.

## `program.md` template for AIC

```markdown
# AIC Autoresearch — program.md

## What we optimize
**Primary metric**: `tier_3_mean` from frozen evaluator. (Higher = better.)
**Secondary**: `total_score`. Reported but not the merge gate.
**Sanity**: `valid` must be true; otherwise revert.

## Scope of edits
- ALLOWED: `train_policy.py`, `config.yaml`.
- FORBIDDEN: anything in `data/`, `eval/`, `engine/`, `controllers/`, `assets/`,
  `aic_engine/`, `aic_controller/`, `aic_engine/config/`. These are part of the harness.

## Hypotheses to test (in priority order)
1. F/T-conditioned ACT > vanilla ACT.
2. DINOv2-frozen encoder > ResNet-18 trained.
3. Aggressive image DR > mild DR.
4. Chunk size K=32 > K=8 for our task.
5. Diffusion Policy > ACT (separate config).

## Revert criteria
- Any NaN in loss → revert.
- Training time > 12 hours → revert (timebox).
- Eval `valid` == false → revert.
- New metric < current `main` metric → revert.

## Forbidden behaviors (catch reward hacking)
- Do NOT change the eval harness or `scoring.yaml` schema.
- Do NOT introduce side effects in train script that affect eval (writing to shared dirs).
- Do NOT skip the eval (the harness must run at least 3 trials).

## How to interpret the history
- Last 20 commits include diff + metric. Read them. Don't repeat losing changes.
- If you see a regression cluster, switch hypothesis.
```

## Time boxing

- **Per-iteration timebox**: 90 minutes (training) + 30 minutes (eval) = 2 hours max.
- **Overnight target**: 8-10 iterations / night.
- **Weekly target**: 50-70 iterations.

If a training run hangs past 2 hours, kill it, mark as `valid=false`, archive, continue.

## Sweep axes (Phase 1)

```yaml
# config.yaml axes Codex is free to sweep
policy: [bc, act, diffusion, vqbet]
encoder: [resnet18, dinov2-frozen, dinov2-lora-rank8]
chunk_size: [8, 16, 32]
batch: [16, 32, 64]
lr: [1e-5, 3e-5, 1e-4, 3e-4]
augmentation: [none, light, aggressive]
ft_concat: [true, false]
ft_dropout: [0.0, 0.25, 0.5]
dr_strength: [0.0, 0.3, 0.6, 1.0]
task_conditioning: [none, one_hot, text]
demo_subset: [all, successful_only, balanced]
```

That's ~24,000 combinations. Codex prioritizes by archive history; we don't grid-search.

## Specific patterns we adopt

### From Karpathy `autoresearch`
- 3-file structure: `prepare.py` (frozen eval), `train.py` (editable), `program.md` (methodology).
- 5-minute training runs initially (we start with 30 min because Gazebo is slow).
- Git-based archive.
- Binary keep/revert based on metric.

### From Eureka
- LLM proposes reward function variants → train RL → return reward component statistics → LLM mutates.
- Useful **specifically for the RL track** (file `09` PPO + Isaac or file `10` Residual RL).
- Run separately, not in the main IL loop.

### From DrEureka
- After a policy is working, the LLM proposes domain-randomization distributions.
- "RAPP" (Reward-Aware Physics Prior): empirical robustness curve as the LLM's prior.
- Specifically for sim-to-eval transfer hardening.

### From AI Scientist v2
- Best-first tree search over experimental branches. Adopt **only if simple linear iteration plateaus** — adds complexity.

### From OpenAI Cookbook (Codex agent improvement loop)
- Codex's role is **narrow**: implement the diff, not decide it. Decisions live in `program.md` and the archive's metrics.
- Don't trust agent self-reports; external eval is the only ground truth.

## What we do NOT use

- **LLM-as-judge in the inner loop.** Tempting but the published failure mode is uniform. Only use LLM-as-judge in the **weekly retrospective**.
- **MCTS / tree search of prompts.** Adds engineering burden; skip in v1.
- **Multi-agent coordination** (Agent Laboratory, AgentRxiv style). Overkill for one task.

## Pitfalls specific to AIC

| Pitfall | Mitigation |
|---|---|
| **Reward hacking the scoring system.** "policy hovers near port to harvest Tier 3 proximity without insertion." | Frozen eval includes 5 trials; Codex never sees inside. Variance in Tier 3 across seeds catches the gameable solutions. |
| **Sim-to-sim drift** between Isaac (training) and Gazebo (eval). | Eval is always Gazebo. If we add Isaac for training throughput, validate on Gazebo every N iterations. |
| **Scoring gameability** of multi-component Tier 2. | Primary metric is `tier_3_mean`; the rest are reported, not gating. |
| **Catastrophic forgetting in the archive.** Codex sees only top-K → narrow funnel. | Index by *config description embedding*, not score. Retrieve diverse exemplars. |
| **Sim crashes vs zero score.** | Distinguish in JSON output (`valid` field). |
| **Wall-clock asymmetry.** GPU is the bottleneck. | Batch 3-5 LLM proposals at once; train each in parallel if Gazebo can multi-instance; pick survivor. |
| **Task drift** (Cerebras failure mode). | Weekly Claude-Code retrospective compares last N commits against `program.md` intent. Alarm if drift > threshold. |
| **Codex hallucinates a dependency.** | Lock pixi env; Codex's worktree inherits the same `pixi.toml`. Any new import must work via `pixi add` (which is in scope; full env edit out of scope). |

## Validation milestones (gate before scaling up)

Before letting the loop run unattended for >24 hours:

1. **Manual run of 1 iteration**, observed start-to-finish. Confirms harness works.
2. **Manual run of 5 iterations**, sequential. Confirms archive + revert logic works.
3. **Manual run of 1 *failed* iteration** (intentional NaN). Confirms safe revert.
4. **24-hour unattended run** with frequent check-ins. Look for task drift, RTF degradation, GPU memory leaks.
5. **48-hour unattended run**. Now we have signal.
6. **Compare against a hand-tuned single-config baseline.** If 48 hours of auto-research can't beat a known-good config, the loop is broken (or the search space is wrong).

## Concrete first build (week 0 if we commit)

1. `eval_harness.sh` — frozen, takes ckpt path + seed, outputs JSON line.
2. `train_policy.py` — minimal LeRobot wrapper that reads `config.yaml`.
3. `program.md` — the methodology.
4. `loop.py` — calls Codex via API, applies patch, runs train, runs eval, commits.
5. Test on 5 iterations with a known config seed-only variation.
6. Run 24 hours; review.

Estimated build effort: **2-3 person-days for v1**. Most cost is in the frozen evaluator (headless Gazebo + scoring) and the Codex API plumbing.

## Codex API specifics

- Set Codex's working dir to the worktree.
- Pass `program.md` + diffs of last 20 commits + their metrics + the current `train_policy.py` + the current `config.yaml`.
- Prompt template:
  ```
  You are a research agent. Read program.md. Read the history. Propose ONE
  experiment by editing train_policy.py and/or config.yaml. Output the diff.
  Do NOT touch anything outside those two files.
  ```
- Cap output tokens.
- Apply diff; revert if it touches forbidden paths.

## Methods this loop is good for

(per the matrix in [`./00_index.md`](./00_index.md))

| Method | Loop fit | Why |
|---|---|---|
| [[il-bc]] | high | Cheap, fast, clear axes |
| [[il-act]] | high | Same |
| [[il-diffusion-policy]] | high | Same |
| [[il-vqbet]] | high | Same |
| [[il-force-aware]] | high | Same; just extend axes |
| [[repr-autoencoder]] | high | Two-stage: pretrain AE → train head; cheap inner loop |
| [[repr-pretrained]] | medium | Discrete encoder choice; smaller axis |
| [[rl-residual]] | medium | Each iter is hours not minutes |
| [[hybrid-classical-learned]] | medium | Mixed sub-loops |
| [[rl-ppo-isaac]] | medium | Long iters; better via Eureka separately |
| [[rl-hil-serl]] | low | Slow online RL iters |
| VLAs (files 13-16) | low | Each iter very expensive |
| [[il-3d]], [[il-equivariant]] | medium | Specialized |

## Cross-refs

- Inspirations: Karpathy `autoresearch`, Eureka, DrEureka, AI Scientist v2, OpenAI Codex cookbook.
- Eureka-style reward generation specifically: [[auto-eureka]] ([`./11_auto_eureka.md`](./11_auto_eureka.md)).
- Pipeline this loop drives: [[auto-pipeline-design]] ([`./10_auto_pipeline_design.md`](./10_auto_pipeline_design.md)) for data + [[online-gazebo-auto]] ([`./05_online_gazebo_auto.md`](./05_online_gazebo_auto.md)) for eval.
- Distribution-design discipline: [[distribution-design]] ([`./09_distribution_design.md`](./09_distribution_design.md)).
- The decision log entry making this a project goal: [[01-decisions-log]] (in `../07_team/01_decisions_log.md`).

## References (URLs for the team)

- Karpathy `autoresearch`: <https://github.com/karpathy/autoresearch>
- Karpathy announcement (X): <https://x.com/karpathy/status/2030371219518931079>
- Cerebras "stop your autoresearch loop from cheating": <https://www.cerebras.ai/blog/how-to-stop-your-autoresearch-loop-from-cheating>
- Eureka: <https://github.com/eureka-research/Eureka>, paper arXiv 2310.12931
- DrEureka: <https://github.com/eureka-research/DrEureka>, paper arXiv 2406.01967
- AI Scientist v2: <https://github.com/SakanaAI/AI-Scientist-v2>, paper arXiv 2504.08066
- Voyager (skill library pattern): <https://github.com/MineDojo/Voyager>
- OpenAI Cookbook: <https://developers.openai.com/cookbook/examples/agents_sdk/agent_improvement_loop>
- AlphaEvolve / FunSearch (propose-evaluate-archive in math/algorithms).
