# Challenge Overview

## What it is

**AI for Industry Challenge (AIC)** — an open robotics competition run by Intrinsic (with NVIDIA and Google DeepMind) on the problem of **dexterous cable insertion** for electronics assembly. Specifically: routing and inserting fiber-optic connectors (SFP modules, SC plugs) into ports on a randomized task board.

Upstream landing: [`docs/overview.md`](../../docs/overview.md). Event page: <https://www.intrinsic.ai/events/ai-for-industry-challenge>.

## Why it is hard

- **Contact-rich manipulation.** Tight tolerances, force-sensitive insertions.
- **Flexible cables.** The cable is compliant, so the dynamics from gripper to plug tip are not rigid.
- **Sim-to-real.** Top teams must transfer policies to a physical workcell at Intrinsic HQ for Phase 2.
- **Generalization.** Trials randomize task-board pose, NIC rail selection, port placement; one policy must handle both SFP→NIC and SC→port insertions.

## What we submit

A **container** that starts a ROS 2 Lifecycle node named `aic_model`. The node receives an `InsertCable` action goal (with a `Task` describing the target plug/port) and commands the robot via `/aic_controller/pose_commands` (Cartesian) or `/aic_controller/joint_commands` (joint). See [`../02_interfaces/`](../02_interfaces/).

## Stakes

- **Prize pool:** $180,000 shared across the top 5 finalists.
- **Funnel:** ~unlimited → top 30 (Qualification) → top 10 (Phase 1) → top 5 (Phase 2).

## Where we are

We are in **Qualification**. Submission window is May 18–27, top 30 announced May 28. See [`01_phases.md`](./01_phases.md) for full dates.

## How we are scored

Three trials × max 100 points each = **300 points** total. Tiers:
1. **Validity** (0/1) — does the model load and conform to the lifecycle?
2. **Performance** (≤ +24, ≥ −36) — smoothness, duration, efficiency, force/contact penalties.
3. **Task success** (−12 to +75 per trial) — full insertion, partial insertion, or proximity.

See [`04_scoring.md`](./04_scoring.md).
