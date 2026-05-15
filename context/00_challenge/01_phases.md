# Competition Phases

Source: [`docs/phases.md`](../../docs/phases.md), [`docs/overview.md`](../../docs/overview.md).

## Timeline

| Phase | Window | Eval Window | Cut |
| --- | --- | --- | --- |
| **Qualification** | Mar 2 – May 15, 2026 | May 18 – 27 | Top 30 announced **May 28** |
| **Phase 1 (Flowstate)** | May 28 – Jul 14 | Jul 14 – 21 | Top 10 announced **Jul 22** |
| **Phase 2 (Real robot)** | Jul 27 – Aug 25 | Aug 26 – Sep 4 | Winner **Sep 8** |

> **Today** is 2026-05-14. Qualification submission window closes **tomorrow**. Our daily submission cap is 1 image.

## Phase 1 — Qualification (where we are)

- **Where:** Local Gazebo (the `aic_eval` Docker image).
- **What:** Train a policy. Submit a container. Evaluated on 3 randomized trials.
- **What's randomized at eval:** Task board pose & yaw, which NIC rail (0–4) gets the NIC card, the NIC's translation along the rail and yaw offset, SC port placement along its rail.
- **What's NOT randomized:** Plug-to-port mapping (specified per trial), the robot start pose, the cable type (`sfp_sc_cable`).
- **Hardware match:** Eval cloud node uses 1× NVIDIA L4 (24 GiB VRAM, CUDA 13.0, driver 580). Local dev only needs RTX 2070+ and 8 GiB VRAM.

Detail: [`02_qualification_trials.md`](./02_qualification_trials.md).

## Phase 2 — Flowstate

Top 30 teams get access to **Intrinsic Flowstate** (Intrinsic's IDE for robot programs) and the **Intrinsic Vision Model**. Build a complete cable handling solution (not just insertion). Docs not yet published upstream.

## Phase 3 — Real robot

Deploy to a physical workcell at Intrinsic HQ. Real UR5e, real Hand-E, real ATI AXIA80, real Basler cameras, real plugs and cable. Sim-to-real transfer is the explicit objective.

## Implication for our autoencoder approach

- **Qualification is sim-only**, so we can over-fit to Gazebo if we want — but doing so kills Phase 2 transferability. Domain randomization across Gazebo / Isaac / MuJoCo is the recommended insurance.
- **Phase 1 brings Intrinsic Vision Model** — our autoencoder may compete with or complement it; design our representation so it's swappable.
- **Phase 2 needs real F/T calibration** — sim F/T is tared each episode, real F/T probably won't be as clean.
