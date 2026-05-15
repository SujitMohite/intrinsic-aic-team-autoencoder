# Public Robot-Learning Datasets — Open X-Embodiment, DROID, RT-X

## TL;DR

Massive open-source datasets of robot teleoperation across many platforms. **Open X-Embodiment (OXE)** is the umbrella collection (970k+ episodes from 22 institutions). **DROID** is the largest single dataset (76k demos across 564 scenes on a Franka). **RT-X** is Google's curated subset for VLA pretraining. **For AIC, these are useful only for VLA fine-tuning prerequisites** (the pretrained VLA already absorbed them). We do not need to download / process them ourselves.

## What it produces

- Format: LeRobot v2 parquet or TFRecord depending on dataset.
- Modalities: RGB images, joints, actions, language instructions.
- Size: OXE is ~3 TB total; DROID is ~1 TB; RT-X subset ~500 GB.

## How automatic? — fully automatic (download)

`huggingface_hub.snapshot_download(repo_id="...")` for HF-hosted versions. No human interaction.

## Distribution properties

- **Massive cross-embodiment, cross-task diversity.**
- **Coarse manipulation focus.** Pick, place, push, stack, drawer, fold. **Very little contact-rich / insertion / sub-cm precision data.**
- **No UR5e + Hand-E specifically.** Some Franka, some xArm, some so-101. Cross-embodiment is the point.
- **No F/T sensor in most datasets.** Camera + joints + actions.
- **No SFP / SC / cable** anything.

## Pipeline sketch

For VLA fine-tuning, we don't need our own copy. The pretrained checkpoints (π0, SmolVLA, Octo) have already absorbed these datasets. We just **fine-tune on our keystone dataset** ([`./02_offline_scripted_groundtruth.md`](./02_offline_scripted_groundtruth.md)) using the pretrained VLA's loaded weights.

If we want to **augment our keystone dataset** with public data:
1. Filter OXE for arm + tabletop + insertion-adjacent tasks.
2. Convert to LeRobot v2 format.
3. Mix into our training dataloader with a small sampling weight (~10-20%).

Likely **net negative** for our specific task — the public data is too coarse to help precision and could pull the policy away from our specific contact regime.

## Storage + naming convention

If we do mix: `/data/aic_public/oxe_subset/...` — separate from `/data/aic_demos/`.

## Which methods consume this

| Method | How |
|---|---|
| All VLAs (13, 14, 15, 16) | ★ Via pretrained-checkpoint download. We don't reprocess. |
| Vision encoders (17, 18, 19) | Optional auxiliary pretraining mix. |
| Everything else | Skip. |

## Compute & time

- **Download**: 1-3 days at typical home bandwidth. ★ Don't.
- **Pretrained VLA checkpoint download**: minutes to hours, much smaller.

## Quality gates

We **don't process** these datasets ourselves. Trust the pretrained checkpoints and our own keystone dataset.

## Failure modes

- Time sink to "mix in public data" with no clear gain.
- License compatibility (most OXE is permissive but check before submitting).

## Why we are NOT a primary data path

The pretrained VLA checkpoints already encode this data. Our edge comes from **task-specific** demos (our keystone pipeline), not from re-mixing public data.

## Cross-refs

- Primary alternative: [[offline-scripted-groundtruth]] ([`./02_offline_scripted_groundtruth.md`](./02_offline_scripted_groundtruth.md)).
- Consumers: [[vla-smolvla-pi0]] (file `15`), [[vla-octo]] (file `14`), [[vla-openvla]] (file `13`), [[vla-groot-helix]] (file `16`).
