# Scoring

Source of truth: [`docs/scoring.md`](../../docs/scoring.md), implementation in [`aic_scoring/`](../../aic_scoring/), config in [`aic_engine/config/sample_config.yaml`](../../aic_engine/config/sample_config.yaml).

## Per-trial cap: 100 points. Total cap (3 trials): 300 points.

## Tier 1 — Model Validity (gate)

| Outcome | Pts |
| --- | --- |
| Validation passed | 1 |
| Validation failed | 0 |

Failing this **zeroes the trial** (no Tier 2 or 3 awarded). Conditions:
- `aic_model` is discoverable within 30 s.
- Lifecycle conformance (see [`../03_policy/01_lifecycle_contract.md`](../03_policy/01_lifecycle_contract.md)).
- Issues at least one valid `MotionUpdate` or `JointMotionUpdate` during the task.

## Tier 2 — Performance & Convergence

| Component | Range | Metric | Threshold for max | Threshold for zero |
| --- | --- | --- | --- | --- |
| Trajectory smoothness | 0 to +6 | Avg jerk magnitude (Savitzky–Golay over 15 samples) | jerk = 0 m/s³ | jerk ≥ 50 m/s³ |
| Task duration | 0 to +12 | Elapsed sim time | ≤ 5 s | ≥ 60 s |
| Trajectory efficiency | 0 to +6 | Total Euclidean path of TCP | ≤ initial plug-port distance | ≥ 1 m + initial plug-port distance |
| Insertion force penalty | 0 to −12 | F/T magnitude vs threshold | – | force > 20 N for > 1 s |
| Off-limit contact penalty | 0 to −24 | Robot-link contact with enclosure / task board | – | any contact |

**Gating on Tier 3:**
The 3 positive Tier-2 components (smoothness, duration, efficiency) are only awarded if Tier 3 > 0, i.e. if the plug ends within the "max acceptable distance" of the target port. Penalties are always applied.

Implication: **a fast wave-arm gets nothing**. We must approach the port to harvest any Tier 2 reward.

## Tier 3 — Task Success

### Successful insertion

| Outcome | Pts |
| --- | --- |
| Plug fully seated in **correct** port (verified by contact sensors) | +75 |
| Plug fully seated in **wrong** port | −12 |

### Partial / proximity

When no full insertion is detected:
- **Partial** (plug tip inside the port bounding box, 5 mm xy tolerance, somewhere between entrance and bottom): 38–50 pts, proportional to depth.
- **Proximity** (plug not inside port): 0–25 pts.
  - At port entrance (or closer): 25 pts.
  - At or beyond `max_distance = 0.5 × (initial plug-port distance)`: 0 pts.
  - Linear in between.

## Final score

```
trial_score = Tier1 + Tier2_sum_clamped_to_[-36, +24] + Tier3
final_score = sum(trial_score for each trial)
```

Per-trial theoretical max: 1 + 24 + 75 = **100**.

## Results file

`scoring.yaml` lands in `AIC_RESULTS_DIR` (default `~/aic_results/`). It is **overwritten each run** — set a unique dir per experiment:

```bash
AIC_RESULTS_DIR=~/aic_results/run_2026_05_14_ae_v1 \
  ros2 launch aic_bringup aic_gz_bringup.launch.py ground_truth:=false start_aic_engine:=true
```

See [`../05_evaluation/02_results_files.md`](../05_evaluation/02_results_files.md) for parsing.

## Score-shaping intuition

| What helps | What hurts |
| --- | --- |
| Reach the port → unlocks all Tier 2 positives | Waving without converging → 0 |
| Smooth low-jerk approach (good damping) | Snapping commands (SpeedDemon problem) |
| Direct path | Spiral search beyond 1 m of extra distance |
| Light contact, hold force < 20 N | Pressing > 20 N for > 1 s |
| Stay clear of enclosure/board with the arm | Touching enclosure with forearm → −24 immediately |
| Correct port | Inserting into the wrong port: −12 (worse than not inserting) |

## "Cheat" awareness

`CheatCode.py` uses TF ground truth — it reads exact plug & port poses, applies PID. It is the **upper bound** of what's possible on this scoring scheme (~75 + Tier 2 = ~90+/trial). Use its score as a benchmark for our policy.
