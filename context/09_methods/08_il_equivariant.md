# SE(3)-Equivariant Policies — EquiBot, ET-SEED, EquiAct

## TL;DR

**Bake rotational and translational symmetry into the network**: a rotated input causes an exactly rotated output. The headline promise is **5× sample efficiency** from symmetry priors — useful when demos are scarce. Most relevant for tasks where the target object orientation varies widely. **EquiBot** (SIM(3)-equivariant Diffusion Policy), **ET-SEED** (trajectory-level SE(3)-equivariant diffusion with relaxed Markov kernel), **EquiAct** (equivariant ACT). For AIC, equivariance gives free generalization to board pose / NIC yaw — but the engineering cost is high and gains over a well-augmented baseline are modest.

## Why this could work for AIC

- **Board / NIC pose randomization is naturally addressed.** Equivariant nets generalize to rotations and translations exactly, not approximately.
- **Sample efficiency.** Could matter if our keystone pipeline is slow to produce demos.
- **Useful theoretical backstop**: if the keystone IL methods plateau due to sparse-pose coverage, equivariance is a principled fix.

## Why this could fail for AIC (skeptical)

- **Engineering cost.** e3nn / equivariant layers are 2-3× slower at runtime than dense layers. Custom implementation; no LeRobot first-class support.
- **No F/T fusion native.** Adds another bolt-on.
- **Gains often disappear with aggressive image augmentation + good DR.** A 2D Diffusion Policy with strong rotational augmentation may match equivariant nets in practice.
- **Few practitioners.** Hard to debug; small community.
- **No published 5 mm cable insertion** with equivariant policy.

## Generalization analysis

| Axis | Generalizes? | Notes |
|---|---|---|
| NIC index 0–4 | strong | Standard. |
| Board pose & yaw | **excellent natively** | The pitch. |
| Plug type | weak; needs conditioning | Geometry differs; explicit branch. |
| Grasp-pose noise | moderate | Symmetric to grasp noise on rotation axes. |
| Lighting | depends on encoder | Equivariance is over rotation/translation, not photometry. |
| Sim-to-real | strong | Symmetry is invariant. |

## Key resources

| Resource | Year | What |
|---|---|---|
| Yang et al., "EquiBot" (CoRL 2024) | 2024 | arXiv 2407.01479. <https://github.com/yjy0625/equibot> |
| Tie et al., "ET-SEED" (ICLR 2025) | 2024 | arXiv 2411.03990. <https://github.com/tie1998/ET-SEED> |
| "EquiAct" | 2024 | ICRA 2024; equivariant ACT analog. |
| `e3nn` library | maintained | Equivariant layers in PyTorch. |

## Data needs

- 40-100 demos sufficient (equivariance is sample-efficient).
- Same data source as [[il-diffusion-policy]] / [[il-act]] (keystone pipeline).
- Distribution: cover plug type and grasp variation; the rotation axis is *not* a problem.

## Compute & time

- Training: 8-12 hours (equivariant nets slower).
- Inference: 100-150 ms with denoising. Tight.
- VRAM: 16 GB fits.

## Auto-research applicability — **medium-low**

Specialized architecture; few standard knobs to vary. Limited fit for autoresearch.

## My note: top-30 probability — **moderate**

Modest expected gain over a well-augmented 2D Diffusion Policy. **Don't pursue unless our baseline IL plateaus specifically on pose generalization** (i.e. fails on extreme NIC yaw or board orientations).

## Priority for our project — **4 of 5**

- Defer; not a first-attempt.
- Revisit if sparse-pose generalization is the failure mode we observe.

## Cross-refs

- Bases: [[il-act]] (file `03`), [[il-diffusion-policy]] (file `04`).
- Alternative: aggressive rotational augmentation in [[synthetic-dr]] ([`../10_data/08_synthetic_dr.md`](../10_data/08_synthetic_dr.md)) may match equivariance with less engineering.
