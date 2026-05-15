# Context — Team Autoencoder

Modular, agent-friendly project context. Each file is **self-contained** so any one can be loaded into an LLM context window independently, without dragging in the whole bundle.

If you only have time for one thing, read [`/CLAUDE.md`](../CLAUDE.md).

---

## Layout

```
context/
├── 00_challenge/        What we are solving
│   ├── 00_overview.md           Mission, prizes, who runs it
│   ├── 01_phases.md             Qualification → Phase 1 → Phase 2 timeline
│   ├── 02_qualification_trials.md   The 3 sim trials (SFP×2, SC×1)
│   ├── 03_rules_compliance.md   What's allowed and what disqualifies us
│   └── 04_scoring.md            Tiered scoring breakdown
│
├── 01_environment/      The sim & toolkit infrastructure
│   ├── 00_setup.md              Pixi + Docker + distrobox + NVIDIA
│   ├── 01_scene.md              Robot, sensors, world
│   ├── 02_task_board.md         Rails, mounts, randomization ranges
│   ├── 03_assets_catalog.md     SFP / SC / LC / NIC / cable inventory
│   └── 04_docker_pixi.md        Container & package management mental model
│
├── 02_interfaces/       The ROS surface available to our policy
│   ├── 00_topic_inventory.md    Inputs/outputs at a glance
│   ├── 01_observation_msg.md    What our policy sees (cameras, FT, joints)
│   ├── 02_motion_messages.md    MotionUpdate / JointMotionUpdate fields
│   ├── 03_task_action.md        Task.msg + InsertCable.action
│   └── 04_controller.md         Impedance ctrl, modes, tare
│
├── 03_policy/           What we implement
│   ├── 00_framework.md          aic_model + Policy ABC
│   ├── 01_lifecycle_contract.md Lifecycle states & timeouts
│   ├── 02_baselines.md          Each baseline policy explained
│   ├── 03_writing_a_policy.md   Step-by-step recipe for a new policy
│   └── 04_pitfalls.md           Things that break submissions silently
│
├── 04_training/         Off-policy training stacks
│   ├── 00_overview.md           Multi-sim strategy & data flow
│   ├── 01_teleop_data.md        Keyboard teleop + data collection
│   ├── 02_lerobot.md            LeRobot / ACT imitation learning
│   ├── 03_isaac_lab.md          NVIDIA Isaac Lab integration
│   └── 04_mujoco.md             MuJoCo MJCF + ros2_control
│
├── 05_evaluation/       Local scoring & regression checking
│   ├── 00_local_eval.md         How to run the engine locally
│   ├── 01_scoring_examples.md   Reproducible scoring-tier exercises
│   └── 02_results_files.md      Reading scoring.yaml
│
├── 06_submission/       Delivery to the portal
│   ├── 00_packaging.md          Dockerfile + docker-compose
│   ├── 01_upload.md             ECR auth + image push
│   └── 02_checklist.md          Pre-flight before clicking Submit
│
├── 07_team/             Our work-in-progress
│   ├── 00_approach.md           Autoencoder approach plan
│   ├── 01_decisions_log.md      ADR-style log of choices
│   ├── 02_experiments.md        Run table with config + score
│   └── 03_resources.md          Hardware inventory, AI tool budget, allocation
│
├── 08_reference/        Look-ups
│   ├── 00_glossary.md           Terms (SFP, LC, TCP, jerk, etc.)
│   └── 01_troubleshooting.md    Common failures and fixes
│
├── 09_methods/          Method landscape research (22 methods + index)
│   ├── 00_index.md              Comparison table, decision guide, recommended top-3
│   ├── 01_classical.md          Visual servo / search / FSM / hybrid pos-force
│   ├── 02-08                    Imitation learning (BC, ACT, Diffusion, VQ-BeT,
│   │                            Force-aware, 3D, Equivariant)
│   ├── 09-12                    Reinforcement learning (PPO+Isaac, Residual, World, HIL-SERL)
│   ├── 13-16                    VLAs (OpenVLA, Octo, SmolVLA+π0, GR00T/Helix)
│   ├── 17-19                    Representation learning (AE, Pretrained, MAE)
│   ├── 20                       LLM planner (niche)
│   └── 21-22                    Hybrids (classical+learned, demo-bootstrapped RL)
│
└── 10_data/             Data-collection strategies (12 + index)
    ├── 00_index.md              Method × data overlap matrix + keystone pipelines
    ├── 01-03                    Offline: teleop, scripted-CheatCode, public datasets
    ├── 04-06                    Online: Isaac parallel, Gazebo headless, MuJoCo CPU
    ├── 07-08                    Self-supervised obs / Synthetic DR
    ├── 09                       Distribution design — what good coverage means
    ├── 10                       Auto pipeline infrastructure
    ├── 11                       Eureka / DrEureka — LLM reward generation
    └── 12                       Karpathy-style auto-research loop design
```

---

## Conventions

- **Cite upstream code.** When stating a fact, link to the file (with line number when useful). Truth lives in code, not in this doc.
- **Cite upstream docs only when our doc adds nothing.** Prefer summarizing the *implication for our team* over restating.
- **Status tags.** Files in `07_team/` may carry `STATUS: draft | accepted | superseded` at the top.
- **Keep files small.** If a file passes ~400 lines, split it.
- **Don't duplicate `docs/`.** That folder is upstream. Our value-add lives here.

---

## Update protocol

When upstream `docs/` or interfaces change:
1. Update the corresponding file in `context/`.
2. Touch `CLAUDE.md` only if the **top-of-mind facts** changed.
3. Note material changes in `07_team/01_decisions_log.md`.
