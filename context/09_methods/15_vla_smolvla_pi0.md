# SmolVLA + π0 / π0.5 — LeRobot-native VLAs

## TL;DR

**SmolVLA** (HuggingFace 2025, 450M params, SmolVLM2 backbone + flow-matching action expert) and **π0 / π0.5** (Physical Intelligence 2024-25, 3.3B params, PaliGemma backbone) are the two **LeRobot first-class** Vision-Language-Action foundation models. Both are pretrained on cross-embodiment data and fine-tune to specific platforms with 50-200 demos. They sit on opposite ends of a size/quality tradeoff: **SmolVLA fits 16 GB cleanly** and is best for "drop in and try"; **π0 needs LoRA + freeze-VLM** at our VRAM budget and offers higher headroom. Both natively use action chunking and pair with **Real-Time Chunking (RTC)** to hide their 30-100 ms inference latency.

## Why this could work for AIC

- **LeRobot first-class.** `pixi run lerobot-train --policy.type=smolvla` works out of the box. Same for `pi0`.
- **Cross-embodiment pretraining** = robust feature representations from much more data than we could collect. Specifically helps with vision generalization across NIC indices and board poses.
- **SmolVLA designed for consumer hardware** — 450M params train comfortably on 16 GB.
- **π0's flow-matching action expert** generates smooth chunks of length 50, matching the natural horizon of an insertion attempt.
- **F/T can be appended to state vector.** ForceVLA paper (which uses π0 backbone) shows this gives +23.2% over vanilla π0. ★ A π0 + F/T concat is a credible attempt.

## Why this could fail for AIC (skeptical)

- **Pretraining data didn't include sub-cm contact-rich tasks.** SmolVLA was trained on LeRobot community datasets (mostly pick-place + sort + stack). π0 on cross-embodiment teleop, again coarse. **5 mm tolerance is below the precision regime of the pretrain**.
- **π0 needs LoRA + freeze-VLM + bf16 + train_expert_only=true** to fit 16 GB. Even then, batch size is small. The published numbers come from full fine-tuning on much bigger GPUs.
- **F/T is bolt-on, not native.** Both SmolVLA and π0 ingest "state" but their pretraining didn't see F/T-conditioned demos. Whether they actually *learn* to use F/T effectively in a small fine-tune set is unknown.
- **VLA fine-tuning's main strength is multi-task generalization**, not single-task precision. We have one task (cable insertion); a smaller dedicated policy ([[il-force-aware]]) may beat a fine-tuned VLA on the specific task.
- **Latency**. SmolVLA 30-50 ms, π0 70-100 ms per chunk on L4-class. Borderline; RTC mandatory.
- **OpenVLA-OFT (covered in file `13`) is OUT — needs 24 GB minimum.** This file is the surviving VLA shortlist for us.

## Generalization analysis

| Axis | Generalizes? | Notes |
|---|---|---|
| NIC index 0–4 | **strong** | Cross-embodiment pretraining gives strong visual generalization. |
| Board pose & yaw | **strong** | Same. |
| Plug type (SFP / SC) | strong if conditioned with text or task token | Both support language conditioning natively. |
| Grasp-pose noise | moderate-strong | F/T-augmented version is better. |
| Lighting / texture | strong | The headline strength of pretrained foundation models. |
| Sim-to-real | strong | If we ever go Phase 2, this is where these methods shine. |

## SmolVLA in detail

- **Size**: 450M params (SmolVLM2 200M + flow-matching action expert 250M).
- **Pretrain**: 487 LeRobot community datasets, ~10M frames.
- **LIBERO**: 87.3% avg suite success, matching/beating π0 at 1/7 the size.
- **Inference**: 30-50 ms per chunk on L4.
- **VRAM**: trains on a single 4090/3090; fits 16 GB at batch 8.
- **HF Hub model**: `lerobot/smolvla_base`.
- **Docs**: <https://huggingface.co/docs/lerobot/smolvla>.

**For AIC**: best single-shot "drop into LeRobot" VLA. Lowest engineering cost.

## π0 / π0.5 in detail

- **π0 size**: 3.3B params (PaliGemma 3B VLM + 300M flow-matching action expert).
- **π0.5**: open-world generalization variant. Sep 2025.
- **π0-FAST**: autoregressive variant using FAST tokenizer (DCT-based action compression).
- **Pretrain**: 10k hours across cross-embodiment robots.
- **Reported performance**: outperforms Octo, OpenVLA on cross-embodiment manipulation.
- **VRAM (16 GB constraint)**:
  - Full FT: needs 80 GB GPUs.
  - **LoRA + freeze VLM + bf16 + small batch**: fits 16 GB. Per the 2512.11921 paper, even 8 GB cards have been demonstrated.
  - On-the-edge but possible.
- **Inference**: ~73 ms per chunk on RTX 4090 with 3-cam input + 50-action chunk. RTC hides this.
- **HF Hub model**: `lerobot/pi0`, `lerobot/pi05`, `lerobot/pi0fast`.
- **Open source**: `Physical-Intelligence/openpi` (JAX + PyTorch).

**For AIC**: higher ceiling than SmolVLA; higher engineering risk + cost.

## Method ingredients (both SmolVLA and π0)

```
[Text instruction: "insert SFP plug into sfp_port_0 on nic_card_2"] → text tokens
[3 cams 224×224 each] → image tokens (one per patch grid)
[F/T (6), joints (6), TCP_pose (6)] → state tokens
                                       ↓
                                       Transformer encoder (VLM)
                                       ↓
                                       Action expert (flow matching or autoregressive)
                                       ↓
                                       Action chunk (length 50)
                                       ↓ (RTC at inference)
                                       Robot
```

Key additions for AIC:
- **F/T in state vector** (Bi-ACT-style bolt-on). Same trick as [[il-force-aware]].
- **Task language**: generate per-trial from `task.plug_type` and `task.port_name`. The text branch of the VLM gives us free goal conditioning.
- **RTC mandatory** at inference.

## Key resources

| Resource | Year | What |
|---|---|---|
| Shukor et al., "SmolVLA" | 2025 | arXiv 2506.01844 |
| Black et al., "π0" | 2024 | arXiv 2410.24164 |
| "π0.5" (open-world) | 2025 | arXiv 2504.16054 |
| "π0-FAST" | 2025 | arXiv 2501.09747 |
| Yu et al., "ForceVLA" (π0 + force MoE) | 2025 | arXiv 2505.22159; 80% plug insertion. **Most relevant variant for AIC.** |
| Pertsch et al., "FAST tokenizer" | 2025 | arXiv 2501.09747 |
| **`huggingface/lerobot`** | maintained | First-class smolvla, pi0, pi05, pi0fast policies. |
| **`Physical-Intelligence/openpi`** | maintained | π0 reference impl. |
| LeRobot blog: π0 + SO-101 fine-tune tutorial | maintained | <https://huggingface.co/blog/nvidia/gr00t-n1-5-so101-tuning> (analogous workflow) |
| 2512.11921 — "LoRA-Based Fine-Tuning of VLAs on 8GB" | 2025 | Validates feasibility of π0 LoRA on small cards. |

## Data needs

- **Type**: (obs, action, text instruction) — LeRobot v2 dataset format.
- **Amount**: 50-500 demos per task variant. Reach 500-2000 total across our (NIC × plug) buckets.
- **Distribution requirements**: same as IL family. The pretrain handles broad invariance; we need to cover task-specific variation.
- **Collection strategy**: [`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md). Add a `task_text` column synthesizing the Task message into a natural-language string.
- **Overlap**: same demos as ACT / DP / VQ-BeT / F/T-IL. The text-instruction column is the only addition.

## Compute & time

**SmolVLA**:
- LoRA FT on 1000 demos: ~6-10 hours on RTX 2000 Ada.
- Inference: 30-50 ms / chunk. RTC hides.

**π0**:
- LoRA + freeze-VLM FT on 1000 demos: ~18-30 hours on RTX 2000 Ada. Tight.
- Inference: ~80 ms / chunk on L4. RTC hides.

**Total wall-clock (assuming demos ready)**: SmolVLA in a day; π0 in 2-3 days.

## Best simulation environment

**Gazebo** for fine-tuning and eval. The pretrain handles broad visual variation; we don't need cross-sim DR for the VLA itself. (Cross-sim DR still useful at the demo-collection stage to broaden the training distribution.)

## Auto-research applicability

**Medium fit.**

Tunable axes:
- LoRA rank (4, 8, 16, 32)
- Which layers to LoRA (VLM only / action expert only / both)
- Text-prompt format
- F/T concat dimension
- Chunk length
- DR strength

Iteration: ~12-24 hours per π0 config; faster for SmolVLA (~6-10 hr). Karpathy fit: **medium** — slow per iter, but the LoRA rank sweep is exactly what autoresearch handles well.

## My note: top-30 probability — **moderate**

VLAs are tempting but the bet pays off in specific scenarios:
- **If our task-language conditioning helps generalization** across NIC + plug type → SmolVLA shines.
- **If the cross-embodiment pretrain transfers** to our wrist-camera setup → π0 shines.
- **If neither happens** (likely if our demos are highly task-specific) → a smaller dedicated F/T-ACT may match or beat both at lower compute.

**Best case** (π0 + LoRA + F/T + RTC + DR): 60-70 Tier 3 / trial × 3 = 180-210, Tier 2 ~20 each → **240-270 total**. Top-30 plausible.

**Likely case**: 40-55 Tier 3 / trial × 3 = 120-165 → mid-pack.

**Risk factors**:
- 16 GB constraint forces small batch + LoRA, which may underfit precision-demanding insertion.
- π0 inference 70-100 ms even with RTC may miss deadlines if Gazebo RTF drops.
- The "VLA is overkill for one task" argument is real.

## Priority for our project — **3 of 5**

- **SmolVLA** is worth a one-day "try and measure" attempt because the engineering cost is low (LeRobot ships it).
- **π0** is a higher-ceiling, higher-cost backup. Only invest if SmolVLA shows promise.
- **ForceVLA on π0** is the most exciting variant but the code wasn't released at the agent's research time (2025). Worth checking again later.
- Do NOT compete priority 1-2 slots; secondary parallel attempt.

## Cross-refs

- VLA siblings: [[vla-openvla]] (file `13`) — skip due to 24 GB; [[vla-octo]] (file `14`); [[vla-groot-helix]] (file `16`).
- Force-aware extension: [[il-force-aware]] (file `06`); ForceVLA on π0 backbone is the direct integration.
- Demo data: same as IL family. [[offline-scripted-groundtruth]] ([`../10_data/02_offline_scripted_groundtruth.md`](../10_data/02_offline_scripted_groundtruth.md)).
- Public pretraining context: [[offline-public-datasets]] ([`../10_data/03_offline_public_datasets.md`](../10_data/03_offline_public_datasets.md)).
- RTC inference trick: applies to any chunked policy — see also [[il-diffusion-policy]] (file `04`).
