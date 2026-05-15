# Self-Supervised Observation Collection — for AE / MAE / Encoder Pretrain

## TL;DR

Collect **observation-only** data (no actions, no labels) by running ANY policy — including random / wave-arm — across the full Gazebo randomization range. The goal is to maximize **visual diversity** in the dataset, not task success. Outputs feed [[repr-autoencoder]] (file `17`), [[repr-mae]] (file `19`), and frozen-encoder LoRA fine-tunes. **The cheapest data we can produce; the most leverage when paired with a learned visual front-end.**

## What it produces

- **Format**: image dataset (PNG / JPG or compressed tensors), plus optional state context for multimodal AE.
- **Modalities**: 3 cameras (RGB), F/T, joint positions. No actions, no labels needed.
- **Order-of-magnitude**: 10k–100k frames easily; ~10k frames/hour passive collection.

## How automatic? — fully automatic

Run a "scanning" policy (slow joint sweep, random WaveArm, or CheatCode itself) in headless Gazebo and dump frames at 5-10 Hz. No human in loop.

## Distribution properties

- **Cover the full visual hypercube**: NIC index, board pose, plug type, lighting (if we permute), camera occupancy.
- Critically: the **policy's** behaviour doesn't matter for AE training; only what the scene looks like.

## Pipeline sketch

```
For each scene config (NIC, plug, board yaw):
  1. Launch headless Gazebo with config.
  2. Run WaveArm (or CheatCode) for ~10 seconds.
  3. Subscribe to /observations, dump every Nth frame to disk.
  4. Move to next config.
```

Optimizations:
- **Use the same Gazebo instance** that the keystone pipeline ([`./02_offline_scripted_groundtruth.md`](./02_offline_scripted_groundtruth.md)) runs — collect AE data as a byproduct.
- **Run a scripted "scanner" policy** that visits diverse joint poses to maximize view diversity.

## Storage + naming convention

```
/data/aic_selfsup/
├── frames/
│   ├── frame_<sim>_<plug>_<NIC>_<seed>_<t>.jpg
│   └── ...
└── manifest.json    (frame metadata)
```

Compression: JPG at 224×224 for AE pretraining is tiny (~10 KB/frame). 100k frames = ~1 GB.

## Which methods consume this

| Method | How |
|---|---|
| [[repr-autoencoder]] (17) | ★ Primary training data for from-scratch β-VAE / VQ-VAE. |
| [[repr-mae]] (19) | ★ Continued MAE pretraining on Gazebo images. |
| [[repr-pretrained]] (18) | Optional LoRA fine-tune of DINOv2 / Theia on our distribution. |
| Port detector (in [[classical]] file `01` and [[hybrid-classical-learned]] file `21`) | Some of these frames can be auto-labeled and used as detector training data. |

## Compute & time

- Collection: 10k frames in ~1 hour.
- Storage: ~1 GB per 100k frames at 224×224.

## Quality gates

- Visual diversity check: t-SNE on a sample of frames; multiple clusters confirms coverage.
- Lighting / GI variations included (run permutations).
- No camera blackouts / missing frames.

## Failure modes

- **Too many "same view" frames** if the policy doesn't vary the arm pose enough. Mitigation: scanner policy with deliberately diverse joints.
- **Compression artifacts** at low quality. Mitigation: JPG quality ≥ 85 or use lossless WebP.

## Cross-refs

- Consumers: [[repr-autoencoder]] (file `17`), [[repr-mae]] (file `19`), [[repr-pretrained]] (file `18`).
- Byproduct of: [[offline-scripted-groundtruth]] ([`./02_offline_scripted_groundtruth.md`](./02_offline_scripted_groundtruth.md)).
- Distribution design: [[distribution-design]] ([`./09_distribution_design.md`](./09_distribution_design.md)).
