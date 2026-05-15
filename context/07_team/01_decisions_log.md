# Decisions Log

ADR-style log of choices that affect the work. Each entry: **date · decision · why · alternatives considered · status**.

Add new entries at the **top**.

---

## 2026-05-14 — Desktop is the single primary compute box

**Decision:** Run everything sim/training/submission-related on the Xeon + RTX 2000 Ada 16 GB desktop. Laptop 1 (T1000 4 GB) used only for code editing / Git / docs / SSH. Laptop 2 (RTX 4070) explicitly excluded.

**Why:**
- Desktop GPU is sm_89 — same compute capability as the eval cloud's NVIDIA L4. What trains here should run on the cloud unmodified.
- Laptop 1's Quadro T1000 is **below** the AIC minimum (4 GB VRAM vs. 8 GB minimum) and will not run Gazebo with global illumination at usable RTF.
- Single workflow location reduces dataset/checkpoint sync overhead.

**Alternatives:**
- Bring Laptop 2 back into rotation as a training node (declined — team preference).
- Cloud GPU rental for training (out of scope; no provisioning time before May 15).

**Risks / mitigations:**
- Single point of failure on the desktop. Mitigate by pushing checkpoints off-box daily and tagging a fallback submission image early.
- 16 GB VRAM caps training batch size vs. eval cloud's 24 GB — fits in margin for our planned models.

**Status:** Accepted. See [`03_resources.md`](./03_resources.md).

---

## 2026-05-14 — Split AI tooling: Codex for throughput, Claude for reasoning

**Decision:** Use Codex (unlimited) for scaffolding, boilerplate, tests, repetitive edits. Reserve Claude Code budget ($550) for architectural decisions, cross-file debugging, and post-mortems.

**Why:**
- $550 of Opus 4.7 (1M ctx) burns fast on naive uses with full-repo context.
- Codex is well-suited for high-volume, lower-novelty code generation.
- Claude's 1M context and reasoning quality is worth saving for problems Codex can't do well.

**Alternatives:**
- Use Claude for everything (faster ramp but burns budget).
- Use Codex for everything (cheaper, but architectural decisions suffer).

**Status:** Accepted. See [`03_resources.md`](./03_resources.md).

---

## 2026-05-14 — Use `aic_model` framework, not a custom node

**Decision:** Inherit from `aic_model.Policy` and run via `ros2 run aic_model aic_model -p policy:=...`. Don't write a custom ROS 2 node from scratch.

**Why:**
- Lifecycle is fiddly; the wrapper already handles 30 s discovery + lifecycle transitions + action server + cancel.
- All baselines use it; aligns us with the reference implementations.
- Less code to audit before submission.

**Alternatives:**
- Custom node (allowed by rules; more flexibility, much more boilerplate).

**Status:** Accepted.

---

## 2026-05-14 — Context lives in `/context/` at repo root

**Decision:** Modular team context goes in `context/` next to `CLAUDE.md`, not in a sibling `~/ws_aic/src/context/`.

**Why:**
- Co-located with the code it documents.
- Survives `git clone` on a fresh machine.
- The team-autoencoder fork can keep these files without touching upstream `docs/`.

**Alternatives:**
- Sibling directory outside the repo (cleaner separation, but harder to share + version).

**Status:** Accepted.

---

## 2026-05-14 — Tentative approach: goal-conditioned autoencoder (Variant 2)

**Decision:** Plan to pursue a goal-conditioned image autoencoder + small MLP policy head.

**Why:**
- Directly addresses the eval-time gap (no `/scoring/tf` available).
- Latent stays small → fast inference, fits the 30 s discovery budget.
- Reconstruction grounding gives interpretable latents we can debug.

**Alternatives:**
- Variant 1 (plain VAE): simpler but no explicit port grounding.
- Variant 3 (AE + ACT): heavier and overlaps with `RunACT.py`.
- Pure RL in Isaac: high sim-to-eval risk for Qualification deadline.

**Status:** Draft — not yet experimentally validated.

---

## (template)

## YYYY-MM-DD — <short title>

**Decision:**

**Why:**

**Alternatives:**

**Status:** {draft | accepted | superseded by …}
