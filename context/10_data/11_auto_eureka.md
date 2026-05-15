# Eureka / DrEureka — LLM-Generated Rewards + Automated DR

## TL;DR

**NVIDIA Eureka** (Ma et al. 2023) wraps an LLM (GPT-4-class) around a population of candidate reward functions, runs each in parallel-Isaac-Gym RL, and uses **reward-component statistics ("reward reflection")** to mutate the worst-performing terms. **DrEureka** (2024) extends Eureka with **automated domain-randomization tuning** via the "RAPP" prior. Eureka beat human-written rewards on 83% of tasks; DrEureka demonstrated quadruped sim-to-real on a yoga ball with no real-world fine-tuning. **Relevant to AIC ONLY if we pursue RL** (files `09`-`12`, `22`); the LLM's job is reward and DR distribution, the actual RL is PPO/SAC.

## When this matters

- We commit to an RL path ([[rl-ppo-isaac]], [[rl-residual]], [[rl-hil-serl]], [[hybrid-demo-rl]]).
- We've reached the point where reward shaping is the bottleneck.

If we don't commit to RL: skip this file entirely.

## What it produces

- **A reward function as Python code**, written by the LLM, accepted/rejected by RL convergence.
- **A DR distribution as a config**, written by the LLM, gated by RAPP statistics.

## How automatic? — fully automatic

LLM in the loop; no human after initial setup.

## Eureka pipeline

```
1. LLM (GPT-4-class) sees task description + env source code.
2. LLM proposes N reward functions (population size 10-50).
3. Each reward function trained with PPO in parallel Isaac envs.
4. Reward-component statistics returned to LLM.
5. LLM mutates/recombines top-K survivors. Repeat.
6. After M iterations: best reward + best policy.
```

## DrEureka extension

After Eureka finds a viable reward:
1. Roll out the policy under perturbed physics → RAPP (Reward-Aware Physics Prior).
2. LLM proposes DR ranges using RAPP as grounding.
3. Re-train with DR. Validate against sim-vs-sim with deliberately different physics.
4. Repeat until DR is wide enough for transfer.

## Key resources

| Resource | Year | What |
|---|---|---|
| Ma et al., "Eureka" | 2023 | arXiv 2310.12931. <https://github.com/eureka-research/Eureka> |
| Ma et al., "DrEureka" | 2024 | arXiv 2406.01967. <https://github.com/eureka-research/DrEureka> |
| Beyond Reward Design | 2025 | Critique paper; Eureka assumes observation is sufficient. |

## Data needs

- For Eureka: NONE up front (RL generates its own data).
- For DrEureka: a working baseline policy first.

## Compute & time

- Per Eureka iteration: ~1-2 hours of RL training × population.
- Total Eureka run: 5-10 iterations × population 10 = 50-100 RL training runs.
- **On 16 GB Ada with Isaac**, parallel training is constrained — realistic budget: 24-48 hours of unattended compute for a complete Eureka loop.

## Best simulation environment

Isaac Gym / Isaac Lab. The original Eureka uses Isaac Gym specifically because it's GPU-batched.

## Auto-research applicability — **the Eureka pattern IS auto-research for RL**

Eureka is the LLM-in-the-loop pattern applied to reward design. It composes naturally with the Karpathy-style [[auto-research-loop]] ([`./12_auto_research_loop.md`](./12_auto_research_loop.md)) — different scope (Eureka for reward, Karpathy for hyperparameter/architecture).

## Pitfalls specific to AIC

- **Specification gaming**: Eureka optimizes the literal metric in the prompt. If we ask "cable tip near port," the policy hovers near port without inserting. Mitigation: success metric must be terminal-success-only, not intermediate proximity.
- **Eureka assumes observation is sufficient.** If the policy can't *see* what it needs to react to, no reward shape helps. Mitigation: confirm the policy has the right inputs (F/T, vision) before running Eureka on it.
- **Cost of GPT-4 / Claude API calls.** We have unlimited Codex; check if Codex is suitable for Eureka-style code generation (it should be).

## My note: only relevant if RL is primary

For our planned IL-first path (files `04`, `06`), Eureka isn't applicable.

If we pivot to RL later (residual RL on top of IL plateau, or HIL-SERL fine-tune), Eureka becomes a high-value reward-design accelerator.

## Cross-refs

- Auto-research wrapper: [[auto-research-loop]] ([`./12_auto_research_loop.md`](./12_auto_research_loop.md)).
- Consumers: [[rl-ppo-isaac]] (file `09`), [[rl-residual]] (file `10`), [[rl-hil-serl]] (file `12`), [[hybrid-demo-rl]] (file `22`).
- DR layer: [[synthetic-dr]] ([`./08_synthetic_dr.md`](./08_synthetic_dr.md)).
- Online RL substrate: [[online-isaac-parallel]] ([`./04_online_isaac_parallel.md`](./04_online_isaac_parallel.md)).
