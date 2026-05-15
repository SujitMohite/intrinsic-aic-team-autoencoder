# Glossary

Drawn from [`docs/glossary.md`](../../docs/glossary.md), [`docs/aic_interfaces.md`](../../docs/aic_interfaces.md), and code. Tightened for our use.

## Core software blocks

| Term | Meaning |
| --- | --- |
| **`aic_engine`** | The trial orchestrator. Spawns task board, fires `InsertCable`, scores. Off-limits for us to talk to except through the action. |
| **`aic_adapter`** | Sensor fusion node. Produces the time-synced `Observation` aggregate at 20 Hz. |
| **`aic_controller`** | Impedance controller. Cartesian or joint mode. ~500 Hz inner loop. |
| **`aic_model`** | The ROS 2 LifecycleNode that wraps **our policy**. |
| **`aic_scoring`** | The package that computes tiered scores against the live trial. |
| **`aic_bringup`** | Launch files (`aic_gz_bringup.launch.py` is the main one). |
| **`aic_interfaces`** | Custom msgs / srvs / actions (`Task`, `InsertCable`, `MotionUpdate`, …). |

## Roles in our pipeline

| Term | Meaning |
| --- | --- |
| **Policy** | The Python class we write; consumes Observation, emits robot commands. |
| **Model** (ambiguous) | (a) the policy artifact (network weights); (b) sometimes the entire `aic_model` node. Avoid; use "policy" or "checkpoint". |
| **Adapter** | The `aic_adapter` node — between sensors and policy. |
| **Engine** | The `aic_engine` node — orchestrates trials. |
| **Evaluation Component** | Everything provided by organizers (engine + bringup + controller + adapter + scoring). |
| **Participant Component** | Our container (the `aic_model` node + our policy class). |

## Connector hardware

| Term | Meaning |
| --- | --- |
| **SFP** | Small Form-factor Pluggable. Transceiver module. Both plug and port form. |
| **SC** | Subscriber Connector. Fiber-optic connector, larger form factor. |
| **LC** | Lucent Connector. Smaller fiber connector. Not used in qualification. |
| **NIC** | Network Interface Card. Holds 2 SFP ports per card. Up to 5 cards on the board. |
| **Plug** | The connector end being inserted (we hold one of these). |
| **Port** | The hole being inserted into. |
| **Module** | A higher-level component that contains ports (NIC card has SFP ports). |
| **Mount** | The bracket holding a module on a rail. |
| **Rail** | An adjustable slide; the engine randomizes module positions along it. |

## Robot

| Term | Meaning |
| --- | --- |
| **UR5e** | Universal Robots 5e — the 6-DoF arm. |
| **Robotiq Hand-E** | Parallel-jaw gripper at the wrist. |
| **TCP** | Tool Center Point. `gripper/tcp` frame is the "pinch point" between fingertips. |
| **F/T sensor** | Force/torque sensor (ATI AXIA80-M20). Outputs 3 force + 3 torque components. |

## Control

| Term | Meaning |
| --- | --- |
| **Impedance control** | Compliance-based control. Stiffness and damping determine response to deviation. |
| **Cartesian mode** | Controller listens on `/aic_controller/pose_commands` (`MotionUpdate` messages). |
| **Joint mode** | Controller listens on `/aic_controller/joint_commands` (`JointMotionUpdate` messages). |
| **`MotionUpdate`** | Cartesian command msg: pose/velocity, 6×6 stiffness/damping, FF wrench, wrench-feedback gains, mode. |
| **`JointMotionUpdate`** | Joint command msg: per-joint pos/vel/effort, per-joint stiffness/damping, FF torque, mode. |
| **`ChangeTargetMode`** | The service to switch between Cartesian (1) and Joint (2). |

## Sim & training

| Term | Meaning |
| --- | --- |
| **Gazebo** | The eval simulator. |
| **Isaac Lab** | NVIDIA's training simulator. |
| **MuJoCo** | DeepMind's training simulator. |
| **Pixi** | The workspace package manager (Conda + PyPI). |
| **Distrobox** | Tool to enter Docker containers like a native shell. |
| **Zenoh** | The pub-sub middleware under ROS 2 in this challenge. |
| **RMW** | ROS Middleware. Here, `rmw_zenoh_cpp`. |
| **LeRobot** | HuggingFace's robot-learning framework, integrated via `lerobot_robot_aic`. |
| **ACT** | Action Chunking with Transformers (a LeRobot policy class). The `RunACT` baseline uses it. |

## Scoring

| Term | Meaning |
| --- | --- |
| **Tier 1** | Model validity (0/1). Prerequisite. |
| **Tier 2** | Performance: smoothness, duration, efficiency, plus penalties for force & off-limit contact. |
| **Tier 3** | Task success: full insertion (correct/wrong), partial insertion, proximity. |
| **Jerk** | Third derivative of position. Used for the smoothness metric (Savitzky-Golay window of 15 samples). |
| **`scoring.yaml`** | The artifact written by the engine after a run. |

## Coordinate conventions

| Term | Meaning |
| --- | --- |
| **`base_link`** | Robot base frame. World-fixed for our purposes. |
| **`gripper/tcp`** | The TCP frame. Cartesian pose offsets in this frame are relative to current TCP pose. |
| **`/tf`** | The TF tree from robot kinematics. Allowed at eval. |
| **`/tf_static`** | Static frames from URDF. Allowed at eval. |
| **`/scoring/tf`** | Ground-truth poses. **Off-limits at eval.** |
