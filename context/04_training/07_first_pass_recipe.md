# First-pass training recipe — what to actually run

Concrete recipe for the **first** training run on the keystone dataset. Goal: a working policy you can run through the local eval (06) within 1–2 days, targeting top-30 (total ≥ 176 across 3 trials). Optimization comes later.

Reads upstream: [`05_keystone_dataset.md`](./05_keystone_dataset.md), [`06_local_eval_loop.md`](./06_local_eval_loop.md), [`context/09_methods/00_index.md`](../09_methods/00_index.md), [`context/09_methods/04_il_diffusion_policy.md`](../09_methods/04_il_diffusion_policy.md), [`02_lerobot.md`](./02_lerobot.md), [`aic_example_policies/aic_example_policies/ros/RunACT.py`](../../aic_example_policies/aic_example_policies/ros/RunACT.py).

## Pick ONE model class first; don't fork

For the first pass, pick **one** of:

| Model | Pros | Cons | Demo budget |
| --- | --- | --- | --- |
| **ACT** (Action Chunking Transformer) | Already in repo via `RunACT.py`; ~200 demos enough; trains in ~6 h on a single GPU | Slightly worse on noisy demos than diffusion | 200–500 |
| **Diffusion Policy** | Stronger on multimodal action distributions; better for contact-rich tasks per [`context/09_methods/04_il_diffusion_policy.md`](../09_methods/04_il_diffusion_policy.md) | No working ROS wrapper in repo yet; needs ~500+ demos | 500–1000 |

**Recommended for first pass: ACT**, because `RunACT.py` already exists as a ROS-side wrapper and the LeRobot ACT trainer is mature. Diffusion is the v2 upgrade once ACT works.

Do NOT try both in the first pass. One full loop end-to-end first, then iterate.

## Data prep — filtered LeRobot dataset

> **DON'T SKIP THIS.** Training on the raw keystone teaches the policy to fail at insertion. ~⅔ of FastCheatCode trials are open-loop misses (tier_3 partial credit). The mandatory filter drops them. Full rationale + numbers in [`05_keystone_dataset.md`](./05_keystone_dataset.md#critical--filter-before-training).

Before training, build a filtered subset from the raw keystone:

```bash
THRESHOLD=70   # default; raise to 85 for ~60 fewer demos at top quality (see below)
FILTERED=/data/aic_v2/keystone_filtered_t${THRESHOLD}
mkdir -p "$FILTERED"

# 1. Filter manifest rows + copy their parquets.
# 2. Renumber episode_index consecutively.
# 3. Rebuild meta/info.json, meta/episodes.jsonl, meta/stats.json.
# A merge utility for steps 2-3 is NOT yet written — ask Claude to add it
# in data_collection_v2/scripts/build_filtered_dataset.py before the first
# training run.
```

**Threshold cheat sheet** (forecast from 2026-05-14 mini-keystone v2, mean total 79.78, bimodal distribution):

| THRESHOLD | Forecast episodes / 1500 | Use when |
|---|---|---|
| `70` *(default)* | ~870 | First pass; both ACT and Diffusion Policy clear their demo floors |
| `85` | ~810 | Want the cleanest demos; only ~60 fewer than 70 because the distribution is bimodal |
| `50` | ~1380 | Fallback if full keystone underperforms mini and 70-filter yields < 300 |

If the filtered count falls below **300 episodes**, the dataset is too small for Diffusion Policy. Drop the threshold to 50 and accept lower mean quality, or collect more trials before training.

## Hyperparams (ACT, copy-paste defaults)

These are LeRobot's ACT defaults with the only AIC-specific tweaks called out. Adjust only after you've completed one full loop with them.

```python
# Vision encoder input
camera_hw            = (256, 256)        # matches the keystone parquets
camera_names         = ["left", "center", "right"]

# Action / state dims (from the parquet schema)
state_dim            = 25
action_dim           = 13

# ACT specifics
chunk_size           = 32                # 32 × 0.05 s = 1.6 s lookahead
hidden_dim           = 512
n_heads              = 8
n_encoder_layers     = 4
n_decoder_layers     = 7
kl_weight            = 10                # variational ACT default
dim_feedforward      = 3200

# Training
batch_size           = 8                 # 256² × 3 cameras × 8 fits 16 GB
num_steps            = 60_000            # ~6 h on a single GPU
lr                   = 1e-5
weight_decay         = 1e-4
optimizer            = "AdamW"

# Where to write
output_dir           = "/data/training/act_v1"
checkpoint_every     = 5_000
```

Tracking: log to `~/aic_results/training_v1/` so the artifacts live next to the scoring outputs.

## Where to run training

**On Machine A only.** The desktop's RTX 2000 Ada 16 GB sm_89 matches the eval cloud's L4 sm_89, so anything that fits and runs here will fit and run on the portal.

DO NOT train on the laptop with the RTX 4070 (Laptop 2) even though it's faster — it has a different compute capability than the eval cloud, so artifacts compiled there (TorchScript, TensorRT) won't necessarily transfer. Training on A and inferring on A guarantees parity with eval.

DO NOT train on Laptop 1 (T1000 4 GB) — VRAM too low for batch 8 × 256² × 3 cameras.

## Concurrent training + collection: yes, you can

If keystone collection is still running (B still collecting): you can train on A's filtered partial data while A's collection continues. Expect ~25 % throughput loss on both sides (~30 ep/h instead of 42 on A's collection, ~25 % slower training steps). See [`05_keystone_playbook.md` Phase 4](../07_team/05_keystone_playbook.md) for the snapshot pattern.

## Packaging as `aic_model` policy

After training produces a checkpoint, wrap it as a Policy subclass:

```python
# team_autoencoder/policy/act_v1.py
from aic_model.policy import Policy
import torch

class ACTPolicy(Policy):
    def __init__(self, parent_node):
        super().__init__(parent_node)
        self._model = None   # loaded lazily in insert_cable — heavy imports
                             # must NOT block aic_model discovery (30 s budget)

    def insert_cable(self, task, get_observation, move_robot, send_feedback):
        if self._model is None:
            from team_autoencoder.training import load_act
            self._model = load_act("/data/training/act_v1/last.ckpt").cuda()
            self._model.eval()
        # Inference loop:
        #   - get_observation() to read images + state + wrench
        #   - model.predict_action_chunk(obs) → 32-step action
        #   - call move_robot(MotionUpdate(...)) for the next step
        #   - self.sleep_for(0.05) between steps
        ...
        return True
```

Then run [`06_local_eval_loop.md`](./06_local_eval_loop.md)'s command with `policy:=team_autoencoder.policy.act_v1.ACTPolicy`.

## Pass / fail bar for the first pass

The first pass succeeds if:
1. `aic_model` discovers within 30 s (no top-level heavy imports)
2. The policy produces a complete trajectory (no crash) on all 3 local-eval trials
3. Local-eval `total_score` ≥ **100** (≈ ⅓ of cap — proves the policy learned *something*)
4. tier_1 = 1 on all 3 (conformance passes)

If those four hold, package and submit to the portal. If not, the most common failures are:
- **Discovery timeout** → heavy import at top level. Move it inside `insert_cable`.
- **Crash mid-trial** → action dim mismatch, missing image normalization, NaN policy output. Check the policy's action against `aic_control_interfaces/msg/MotionUpdate` field ranges.
- **tier_3 = 0** → policy doesn't descend. Cross-check the training-set action distribution; it should average a clear negative z velocity during the insertion phase.
- **tier_2 < 5** → force spikes from policy over-correcting. Smooth actions (low-pass filter or use the chunk-based action sequence directly).

Once the first pass clears the bar, [`context/07_team/02_experiments.md`](../07_team/02_experiments.md) is the place to log the result and start iterating.

## Out of scope for the first pass

- Force-aware ACT (method 06)
- HIL-SERL fine-tune (method 12)
- Hybrid classical + learned residual (method 21)

All three are in [`context/09_methods/`](../09_methods/) as targets for the *second* pass. The first pass is about closing the loop end-to-end. The second pass is about scoring.
