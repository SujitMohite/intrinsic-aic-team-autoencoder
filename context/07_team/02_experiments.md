# Experiments

Append-only log of every run that produced a `scoring.yaml` or notable observation.

Columns:
- **Run** — short id, ideally `YYYYMMDD-<short_sha>-<note>`
- **Policy** — module path (e.g. `aic_example_policies.ros.CheatCode`)
- **Config** — `ground_truth`, custom config file, anything non-default
- **Total** — total score (300 max)
- **Per trial** — `t1 / t2 / t3` totals
- **Notes** — observations, anomalies, things to investigate

Add new rows at the top.

| Run | Policy | Config | Total | t1 / t2 / t3 | Notes |
| --- | --- | --- | --- | --- | --- |
| _(no runs yet)_ | | | | | |

---

## Detailed notes (long-form)

When a row needs more than fits in a cell, add a section below.

### Template

#### `YYYYMMDD-<id>` — `<one-line summary>`

- **Hypothesis:** What we expected.
- **Setup:** Versions, commit, custom config, env vars.
- **Result:** Numbers + qualitative.
- **What we learned:** New evidence, new questions.
- **Next:** Concrete follow-up.

---

## How to record a run

```bash
RUN_ID="$(date +%Y%m%d)-$(git rev-parse --short HEAD)-ae_v1"
AIC_RESULTS_DIR=~/aic_results/$RUN_ID \
  ros2 launch aic_bringup aic_gz_bringup.launch.py start_aic_engine:=true ground_truth:=false
# After the run, copy summary into the table above.
```

For batch sweeps, write a small Python wrapper that produces a CSV mirroring the table.
