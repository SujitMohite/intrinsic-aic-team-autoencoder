# Synthetic Augmentation + Domain Randomization

## TL;DR

**10× the value of every other dataset cheaply.** Apply visual and physical domain randomization on top of our collected data to multiply effective diversity without re-running the simulator. Visual: color jitter, crop, brightness, Gaussian blur, JPEG compression, lighting shift. Physical: F/T noise injection, action latency, controller stiffness perturbation. **Mandatory for any learning method we care about**; under-investing here is the single biggest preventable risk to generalization.

## What it produces

- **Format**: modified versions of existing parquet datasets (visual aug applied in dataloader at training time, not stored to disk).
- **Modalities**: same as source; perturbed values.
- **Order-of-magnitude**: 5-10× effective data multiplier.

## How automatic? — fully automatic

Applied in the training dataloader as a transform pipeline. Zero human intervention.

## Distribution properties

What it covers (and crucially, what we should configure):

### Visual DR (apply in dataloader)

| Axis | Range | Why |
|---|---|---|
| Random crop | ±10% | Camera position robustness |
| Color jitter | brightness ±0.4, contrast ±0.4, sat ±0.4, hue ±0.05 | Lighting robustness |
| Gaussian blur | σ ∈ [0, 1.5] px | Motion / lens robustness |
| Gaussian noise on image | σ ∈ [0, 8/255] | Sensor noise |
| JPEG compression | quality 60-95 | Compression artifacts |
| Random horizontal flip | **NOT for AIC** | Cable + ports are NOT mirror-symmetric; flipping breaks semantics |
| Random rotation | ±10° | Camera rotation tolerance |
| RandomErase | small patch | Occlusion robustness |

### F/T DR

| Axis | Range | Why |
|---|---|---|
| Additive Gaussian noise on force | σ ∈ [0.1, 0.5] N | F/T sensor noise |
| Additive Gaussian on torque | σ ∈ [0.01, 0.05] N·m | Same |
| Bias drift | offset ∈ [-0.5, 0.5] N | F/T calibration error |
| Sensor dropout | 5% of timesteps | Communication / fault tolerance |

### Action / temporal DR (for RL training)

| Axis | Range | Why |
|---|---|---|
| Action latency | 10-50 ms | Network / control loop delay |
| Action noise | σ ∈ [0, 0.005 m] | Actuation precision |
| Controller stiffness perturbation | ±20% | Match-vs-mismatch with actual hardware |

### Physical DR (Isaac only; for sim-to-sim and sim-to-real)

| Axis | Range | Why |
|---|---|---|
| Mass | 0.8-1.2× nominal | Cable + plug mass uncertainty |
| Friction | 0.5-2× nominal | Contact friction variance |
| Damping | ±30% | Joint friction model error |
| Cable bending stiffness | 0.5-2× | Cable model differs between sims |

## Pipeline sketch

Implemented as a LeRobot dataset transform:

```python
# In our training script (PSEUDO; not yet implemented):
train_dataset = LeRobotDataset("aic_demos")
train_dataset.transform = compose([
    VisualAugment(strength="aggressive"),
    FTNoise(force_sigma=0.3, torque_sigma=0.03),
    JointStateNoise(sigma=0.001),
])
```

For RL, DR is applied at env-construction time in Isaac Lab (or as wrapper layer for Gazebo).

## Which methods consume this

**Every** learning method that consumes images or F/T. The matrix in [`./00_index.md`](./00_index.md) shows ★ for visual policies; F/T augmentation applies to [[il-force-aware]], [[rl-hil-serl]], and any policy with F/T input.

## Compute & time

- **Zero extra compute** for visual aug (applied in dataloader).
- **Negligible RAM** (transform per-batch).
- **Engineering**: ~2 person-days to wire up the transform pipeline and validate.

## Quality gates

- Compare clean-eval vs DR-eval accuracy: DR-trained policies should be approximately as good on clean as on perturbed (within ~5pp).
- Adversarial check: train without DR, evaluate with DR — should drop significantly. Confirms DR matters.

## Failure modes

- **Too aggressive DR** → policy fails on clean eval. Mitigation: anneal DR strength during training.
- **Wrong augmentation axes** (e.g. horizontal flip on AIC: breaks port semantics). Audit the axis list.
- **F/T noise dominates training signal** → policy learns to ignore F/T. Mitigation: tune σ to match real F/T noise scale (calibrate from a no-load tare).
- **DR doesn't transfer to eval** because eval has different perturbation distribution. Mitigation: include DR ranges that bracket eval-cloud variability.

## DR-strength sweep candidates

For autoresearch ([`./12_auto_research_loop.md`](./12_auto_research_loop.md)):
- DR strength: none / mild / medium / aggressive (named presets, not per-axis).
- Per-modality dropout rates.

## Cross-refs

- Applied to data from: every collection strategy in this folder.
- Consumers: every learning method.
- Auto-research lever: [[auto-research-loop]] ([`./12_auto_research_loop.md`](./12_auto_research_loop.md)) treats DR strength as a top-level config axis.
