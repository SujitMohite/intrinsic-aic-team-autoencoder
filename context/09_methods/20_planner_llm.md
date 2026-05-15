# LLM-as-Planner — Code as Policies, VoxPoser, MOO

## TL;DR

**Use a Large Language Model to decompose a high-level instruction into a sequence of skill calls or to write executable code that drives the robot.** Examples: **Code as Policies** (Liang 2022, GPT generates Python that calls perception + motion primitives), **VoxPoser** (Huang 2023, LLM generates voxel-grid value maps), **MOO** (Stone 2023, multimodal object-oriented manipulation). For AIC: **niche fit at best.** Single-task cable insertion does not need multi-step planning; the entire policy is "approach + insert." LLM planners shine in long-horizon multi-skill tasks (kitchen scenarios, multi-step assembly). **Document for completeness; do not pursue.**

## Why this could (in principle) work for AIC

- **Goal conditioning is free.** The Task message can be paraphrased as natural language and fed to the LLM as instruction.
- **Reusability across plug types**: same planner handles SFP and SC if it has the right primitives.
- **Inspectable** — we can see the LLM's plan as code and reason about failures.

## Why this would actually fail (skeptical)

- **AIC is a one-skill task.** "Insert plug into port." There's nothing to plan. Adding an LLM is overhead with no expressive gain.
- **LLM latency is in the seconds range.** Calling it at every observation cycle is infeasible at 20 Hz. Even calling it once per trial adds startup latency that hurts the duration bonus.
- **Eval cloud likely has no LLM API egress.** We'd have to bake a local LLM into the container; 7B+ models eat VRAM that's better spent on the policy.
- **No published cable / connector insertion** result with LLM planners. They live in the kitchen-task / multi-step neighborhood.

## Generalization analysis

Strong on instruction generalization; weak on the precision regime that matters for our task.

## Key resources

| Resource | Year | What |
|---|---|---|
| Liang et al., "Code as Policies" | 2022 | arXiv 2209.07753 |
| Huang et al., "VoxPoser" | 2023 | arXiv 2307.05973 |
| Stone et al., "MOO" | 2023 | arXiv 2303.00905 |
| Lin et al., "Text2Motion" | 2023 | arXiv 2303.12153 |

## Data needs

None for the LLM (zero-shot or few-shot). Primitives (`move_to`, `align_xy`, `insert`) need to be implemented in our toolkit — overlapping with classical / hybrid methods.

## Compute & time

- LLM inference: seconds per call.
- Engineering: ~1 person-week to build the primitive library and LLM-call infrastructure.

## My note: top-30 probability — **low**

Misalignment between the method's strengths (long-horizon planning) and our task (single-skill insertion). **Document and move on.**

## Priority for our project — **5 of 5** (skip)

Skip. If a future phase introduces multi-step assembly (Phase 2 real-robot might), revisit.

## Cross-refs

- Primitives library overlaps with [[classical]] (file `01`) and [[hybrid-classical-learned]] (file `21`).
