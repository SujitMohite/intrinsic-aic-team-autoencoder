# OpenVLA + OpenVLA-OFT — Stanford 7B Vision-Language-Action

## TL;DR

**OpenVLA** (Stanford 2024) is the canonical open-source 7B-param VLA: Prismatic-7B VLM (Llama-2 + DINOv2 + SigLIP) trained on 970k Open X-Embodiment episodes. Autoregressively detokenizes actions; slow. **OpenVLA-OFT** (Feb 2025) overhauls fine-tuning: parallel decoding, action chunking, continuous (not discrete) actions, L1 loss — **26× action throughput, 3× lower latency, 97.1% LIBERO** (vs 76.5% vanilla). Strong on coarse manipulation. **For AIC: the 16 GB VRAM cliff at the fine-tuning stage is the binding constraint — we recommend SKIPPING this method.**

## Why this could (in principle) work for AIC

- Best-documented open-source VLA. Mature community.
- Cross-embodiment pretraining: visual generalization across NIC indices.
- OFT recipe gets 97% LIBERO suite-average — fast for a VLA.

## Why this would actually fail (the killer)

- **LoRA FT requires ≥25.6 GB VRAM at batch=1, bf16** per the repo's own README. Quantization + offload can get inference down to 8 GB, but **training fundamentally targets the 24 GB tier**.
- **Our local hardware is RTX 2000 Ada 16 GB.** Cannot fine-tune cleanly.
- **Eval cloud is L4 24 GB** — could fit training, but we don't have access to do remote training, and the eval cloud is for inference only at submission time.
- **Quantized + offloaded training degrades quality** — published numbers are with full precision.
- **No published sub-cm insertion**. LIBERO tasks are coarse pick-and-place.
- **Inference latency on L4**: ~100-150 ms with OFT parallel decode + 8-step chunk. Borderline.

## Generalization analysis

(Moot given VRAM constraint. Were it to fit: same as SmolVLA / π0 — strong visual generalization, weak F/T fusion natively.)

## Key resources

| Resource | Year | What |
|---|---|---|
| Kim et al., "OpenVLA" | 2024 | arXiv 2406.09246. <https://github.com/openvla/openvla> |
| Kim et al., "OpenVLA-OFT" | 2025 | arXiv 2502.19645. <https://github.com/moojink/openvla-oft> |
| LeRobot | maintained | OpenVLA is NOT first-class in LeRobot. Prefer SmolVLA / π0. |

## Data needs

- 50-200 demos for LoRA FT (same as π0).
- Public OXE pretraining handled.

## Compute & time

- **Cannot reliably fine-tune on our 16 GB hardware.** Period.

## Best simulation environment

N/A — we are not pursuing this.

## Auto-research applicability — **N/A**

## My note: top-30 probability — **low (skip)**

**Recommendation: SKIP.** Use SmolVLA / π0 ([[vla-smolvla-pi0]] file `15`) instead. Same VLA paradigm, fits 16 GB.

## Priority for our project — **5 of 5** (skip)

Document for completeness; don't invest.

## Cross-refs

- LeRobot VLA picks: [[vla-smolvla-pi0]] (file `15`).
- Other VLA options: [[vla-octo]] (file `14`), [[vla-groot-helix]] (file `16`).
