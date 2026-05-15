# Results Files (`scoring.yaml`)

After each engine run, results are written to `${AIC_RESULTS_DIR:-$HOME/aic_results}/scoring.yaml`.

> **Each run overwrites the file.** Set a unique `AIC_RESULTS_DIR` per experiment to keep history.

## Anatomy

(Schema as observed in current toolkit; verify by running CheatCode locally and inspecting.)

```yaml
trials:
  - id: trial_1
    task:
      cable_type: sfp_sc_cable
      plug_type: sfp
      port_name: sfp_port_0
      target_module_name: nic_card_0
      time_limit: 180
    tier_1:
      validity: 1                # 0 or 1
    tier_2:
      smoothness:                # 0..6
      duration:                  # 0..12
      efficiency:                # 0..6
      force_penalty:             # -12..0
      off_limit_penalty:         # -24..0
    tier_3:
      score:                     # -12..75
      insertion_outcome:         # "correct" | "wrong" | "partial" | "proximity" | "none"
      depth: ...                 # if partial
      distance: ...              # if proximity
    total: ...                   # sum
  - id: trial_2
    ...
  - id: trial_3
    ...
total_score: ...
```

## Quick analysis helpers

```bash
# Total score
python -c "import yaml,sys; d=yaml.safe_load(open(sys.argv[1])); print(d.get('total_score'))" \
  ~/aic_results/ae_v3/scoring.yaml

# Per-trial Tier 3 only
python -c "
import yaml, sys
d = yaml.safe_load(open(sys.argv[1]))
for t in d['trials']:
    print(t['id'], t['tier_3']['score'], t['tier_3'].get('insertion_outcome'))
" ~/aic_results/ae_v3/scoring.yaml
```

(Substitute pandas / your favorite spreadsheet if you prefer.)

## What to log alongside

For each run, record (in [`../07_team/02_experiments.md`](../07_team/02_experiments.md)):
- Git commit SHA.
- Policy class & checkpoint path.
- Config: ground_truth flag, custom configs, env vars.
- Total score, per-trial breakdown.
- Anything anomalous in stdout (e.g. force spikes, lifecycle warnings).

## Comparing baselines

Suggested structure:

```
~/aic_results/
├── baselines/
│   ├── cheatcode/scoring.yaml
│   ├── wavearm/scoring.yaml
│   ├── speeddemon/scoring.yaml
│   └── ...
└── experiments/
    ├── 20260514_ae_v1/scoring.yaml
    ├── 20260515_ae_v2/scoring.yaml
    └── ...
```

A simple script that diffs `total_score` across runs is enough early on; promote to a notebook if we want plots.

## Trial seeds

The engine config does not expose a hard seed in `sample_config.yaml`. Randomization is built into trial definitions (poses, NIC index). If we want **reproducibility**, copy `sample_config.yaml` to a custom file with **fixed** trials (set the pose / NIC index explicitly) and point `config_file_path` at it.

> Reproducibility matters when comparing two policy versions locally. The eval uses the published randomized config — only their absolute scores matter at submission time.
