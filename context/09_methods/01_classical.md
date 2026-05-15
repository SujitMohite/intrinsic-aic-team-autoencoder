# Classical Control — Visual Servoing, Search, Compliance, FSM

## TL;DR

Classical control for cable insertion = decompose the task into hand-engineered modules: (a) **visually localize the port** (visual servoing), (b) **align in xy** (search + force feedback), (c) **insert in z** (compliant push). Each module uses a closed-form controller (PID, impedance, Lyapunov-stable). No training data, no GPU at inference, fully interpretable. The classical literature on **peg-in-hole** insertion is huge (back to the 1980s) and remains a strong baseline for industrial deployment.

## Why this could work for AIC

- **Sim-to-eval gap = 0**. Same Gazebo, same controller. What works locally works on the portal.
- **Deterministic.** No randomness in the policy. If it works on one trial, it works on similar trials.
- **No training data needed.** Just engineering. Doesn't depend on data quality (the user's stated #1 worry).
- **Fully respects Tier 2.** Easy to keep jerk low (impedance smoothing), efficient (direct paths), and avoid off-limit contacts.
- **Cheap on the eval clock.** A well-tuned servo lands the plug in 5–15 s — well inside the 60 s duration-bonus cap.

## Why this could fail for AIC (skeptical)

- **Port localization without ground-truth TF is hard.** At eval, `/scoring/tf` is forbidden. We need a **visual port detector** (CV2 contour, fiducial, or small CNN). Each plug/port type may need its own detector. This is where most engineering effort sinks.
- **Brittle to grasp pose noise** (~2 mm, 0.04 rad per the qualification spec). A pure analytic IK from gripper TCP → plug tip → port will miss by exactly that noise. Needs a force-feedback fallback.
- **Two plug families.** SFP and SC look and behave differently. Each gets its own pipeline or a switching layer.
- **Doesn't *learn*.** Every NIC pose, every plug type, every edge case is hand-coded. Maintenance cost compounds.
- **Mostly a baseline, not a top-30 path.** Industrial teams with years of expertise do this well; we'd need to compress that engineering into the project timeline.

## Generalization analysis

| Axis | Generalizes? | Why |
|---|---|---|
| NIC index 0–4 | ✓ (with vision) | The detector finds the port; index doesn't matter to the controller. |
| Board pose & yaw | ✓ (with vision) | Same. |
| Plug type (SFP vs SC) | ✗ unless dual-pipeline | Geometry of the alignment + insertion differs. |
| Grasp-pose noise | weak | Pure feed-forward fails; force-compliance helps. |
| Lighting / texture changes | weak | Hand-tuned vision pipelines are notoriously fragile. |
| Sim-to-sim (Phase 2) | ✗ | Real cameras, real lighting, real cable physics — re-tune from scratch. |

Bottom line: generalizes within the qualification distribution **if** the port detector works. The detector is the soft spot.

## Method ingredients

### 1. Position-Based Visual Servoing (PBVS)

The detector outputs a port pose in camera frame. Robot Jacobian maps desired Cartesian deltas → joint commands. Closed-loop on visual error. Standard, well-understood.

- **Detector options for AIC**: SIFT/AKAZE template matching on the port aperture; small CNN trained on auto-labeled crops from ground truth; pre-trained DINOv2 + clustering. Could pretrain a port-classifier on CheatCode-style auto-collected data.

### 2. Image-Based Visual Servoing (IBVS)

Skip pose estimation; servo directly on image features (port-corner pixel coordinates). Better robustness to camera calibration errors. Convergence proofs exist (Chaumette).

### 3. Spiral / Lissajous search

Once aligned in xy ~ within 5 mm, scan a small spiral while pushing gently in z. F/T senses the entrance edge → align → drop. Used in industrial USB / cable insertion lines.

### 4. Hybrid position/force control (Raibert-Craig formulation, 1981)

Decouple axes into position-controlled (along port axis) and force-controlled (perpendicular). On AIC, the `aic_controller` impedance is already half this — the policy chooses stiffness per axis.

### 5. Finite-state machine

```
APPROACH       ─→ port detection successful → ALIGN
ALIGN          ─→ |xy_err| < 5 mm → SEARCH
SEARCH         ─→ z_force spike → SETTLE
SETTLE         ─→ z_force stable + depth > τ → DONE
DONE           (publish "inserted")
on TIMEOUT or fault → ABORT
```

State variables: visual port pose, F/T magnitude, TCP pose, depth into port.

## Key resources

| Resource | Year | What it is |
|---|---|---|
| Chaumette & Hutchinson, "Visual servo control. Part I" / "Part II", IEEE RAM 2006/07 | 2006-7 | Canonical visual-servoing tutorial. PDF easy to find. |
| Raibert & Craig, "Hybrid Position/Force Control of Manipulators", JDSMC 1981 | 1981 | Founding paper for position-force decoupling. |
| Whitney, "Quasi-Static Assembly of Compliantly Supported Rigid Parts", JDSMC 1982 | 1982 | The first formal analysis of peg-in-hole; remarkably still relevant. |
| Tang, "Industrial Robotic Assembly with Force Control", Industrial Robot 2016 | 2016 | Practical engineering recipes. |
| IndustReal — NVIDIA Industrial Assembly Benchmark | 2024 | Modern eval benchmark — sim2real insertion tasks. <https://industrealkit.github.io/> |
| **Spiral search literature** in connector assembly | various | Search e.g. "robot connector insertion spiral search". |
| **`aic_example_policies/aic_example_policies/ros/CheatCode.py`** | this repo | A *cheating* classical baseline that reads `/scoring/tf` — illegal at eval, but its structure is a template (visual → align → insert). |
| **OpenCV ArUco / ChArUco** | maintained | If we wanted fiducial-based localization (we don't; ports don't have fiducials). |
| **MMDetection / Ultralytics YOLO** | maintained | Lightweight port detector; train on auto-labeled crops from data strategy 02. |

## Data needs

- **None for the controller** itself.
- **Some for the port detector** if we go CNN route: ~500–2000 auto-labeled crops (from CheatCode ground-truth bounding boxes). One day of auto-collection at most. See [`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md) for the collection pipeline; the same pipeline emits detector labels for free if we instrument it.
- **Distribution requirements**: cover all 5 NIC indices, both plug types, varied board yaw, varied lighting (GI on / off).
- **Overlap with other methods**: the detector dataset also serves any vision pipeline (autoencoder pretraining, ACT visual input). So building it is not wasted even if we abandon classical.

## Compute & time

- Training a port detector: a few CPU-hours or ~1 GPU-hour on a YOLOv8n. Trivial.
- Inference: < 5 ms on any GPU; runs comfortably on the Quadro T1000 if needed.
- Wall-clock to build the full FSM + tuner: **1–2 person-weeks of engineering**, mostly chasing edge cases (port-not-detected, F/T noise, controller resets, etc.).

## Best simulation environment

**Gazebo only.** Cable physics + F/T dynamics from another sim won't transfer to the impedance controller's response in Gazebo. Tune the controller in the same sim it's evaluated in.

## Auto-research applicability

**Low fit.** Classical control has few hyperparameters that benefit from automated sweep:

- Tunable axes: search amplitude (1-D scalar), search frequency (1-D), per-axis stiffness (6-D), force threshold (1-D), insertion velocity (1-D). Total ~10 scalars.
- Each evaluation = a Gazebo trial = ~30 s sim time + overhead.
- Even a 1000-rollout grid search finishes in ~10 hours on one desktop. Not interesting for auto-research.
- The **port detector** is a separate auto-research candidate (vary backbone, augmentation, training set size). But that's a vision-training question, not a control-tuning question.

**Karpathy-fit: low.** The classical pipeline rewards human insight (which edge case to handle next), not LLM-driven blind sweep.

## My note: top-30 probability — **moderate**

- **Best case** (port detector works robustly + spiral search lands every cable + impedance tuned tight): **70+ pts/trial × 3 = top-30 plausible**. Similar tasks in the industrial robotics literature get >90% success with well-tuned classical controllers.
- **Likely case**: ~40–60 pts/trial = mid-pack. The detector wins one or two NIC poses, misses others.
- **Worst case**: detector fails on randomized NIC yaw → 0 Tier 3 → ~5 pts/trial = bottom.
- **What it would take to hit top-30 with this method**: a robust port detector that handles all 5 NIC rails + 2 plug types + GI lighting variance. That's the entire game.
- **Risk factors**: any change to Gazebo lighting (GI tweaks, mesh changes) re-breaks the detector; engineering hours dominate.

## Priority for our project — **4 of 5** (do as fallback / baseline)

Strong reasons to build it anyway:
1. **It's the validity guarantee.** A working classical pipeline = a Tier-1-pass submission, hedge against ML approaches that fail discovery or get a near-zero Tier 3.
2. **The port detector reuses across all visual methods.** Building it doesn't compete with our IL/AE work.
3. **Debug tool.** If our Diffusion Policy converges weirdly, the classical FSM tells us whether the *task itself* is solvable in the current Gazebo build.

Reasons against making it primary:
1. **Engineering ceiling**. Top-30 requires polish that a small team in a fixed window can't match against industrial teams.
2. **No upside path to Phase 2.** Classical pipelines re-tune from scratch on real hardware. Learning-based methods at least *attempt* to transfer.

## Cross-refs

- Pairs naturally with [[hybrid-classical-learned]] (file `21`) — use classical for approach, learned for endgame.
- Pairs with [[il-force-aware]] (file `06`) — share the F/T-driven insertion logic.
- Port-detector training data overlaps with [[repr-autoencoder]] (file `17`) — same image distribution.
- Data pipeline → [[offline-scripted-groundtruth]] ([`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md)).
