# Task Board

Source: [`docs/task_board_description.md`](../../docs/task_board_description.md), [`aic_description/urdf/task_board.urdf.xacro`](../../aic_description/urdf/task_board.urdf.xacro), config caps in [`aic_engine/config/sample_config.yaml:46-55`](../../aic_engine/config/sample_config.yaml).

## Zones

| Zone | Function | Components |
| --- | --- | --- |
| 1 | Assembly target | NIC cards with SFP ports (server compute tray) |
| 2 | Assembly target | SC optical ports (patch-panel backplane) |
| 3 | Pick location | SFP modules / LC plugs / SC plugs staged on fixtures |
| 4 | Pick location | Same idea, second pick area |

At eval, only Zones 1 & 2 are *target* zones (the cable is already in our gripper).

## Rails

A "rail" is an adjustable slide. Each runtime randomizes translation (and optionally yaw) along the rail.

| Rail | Count | Translation range (m) | Rotation range |
| --- | --- | --- | --- |
| `nic_rail_0` … `nic_rail_4` | 5 | -0.0215 to +0.0234 (≈ 0.045 m total) | ±10° yaw on the NIC card |
| `sc_rail_0`, `sc_rail_1` | 2 | -0.06 to +0.055 (≈ 0.115 m total) | 0 |
| `lc_mount_rail_0/1`, `sfp_mount_rail_0/1`, `sc_mount_rail_0/1` | 6 (pick zone) | -0.09425 to +0.09425 (≈ 0.189 m total) | ±60° |

## Mounts vs ports

- **Mount** = a fixture that holds something (an NIC card on a NIC rail, or an SFP module on the SFP pick mount).
- **Port** = the *hole* you insert a plug into. SFP ports live on NIC cards (2 per card: `sfp_port_0`, `sfp_port_1`). SC ports live directly on SC mounts.

## Module naming convention

| Module | Up to | Rail family |
| --- | --- | --- |
| NIC cards | `nic_card_0` … `nic_card_4` | `nic_rail_*` |
| SC ports (as standalone modules) | `sc_port_0`, `sc_port_1` | `sc_rail_*` |

The Task message hands us `target_module_name` (the parent, e.g. `nic_card_2`) plus `port_name` (the child, e.g. `sfp_port_1`).

## Randomization at eval

Per trial, the engine:
1. Picks a task_board pose (x, y, z, yaw).
2. Picks which NIC rail holds the NIC card (trials 1 & 2) or which SC rails have a port (trial 3).
3. Picks a translation along the chosen rail.
4. (Trials 1 & 2) Picks a yaw offset for the NIC card on its rail.
5. Spawns the components, attaches the cable to the gripper, fires `InsertCable`.

The published sample_config locks NIC cards 0 and 1, but **NIC card 2 / 3 / 4 are valid at eval**. Test against all 5.

## TF tree (during training, with `ground_truth:=true`)

- `world` → `base_link` (robot base) → `…` → `gripper/tcp`
- `world` → `task_board` → `<rail>` → `<mount>` → `<port>`
- Plug poses are also published when ground truth is on.

During **eval**, only the standard `/tf` (kinematics from joint encoders) and `/tf_static` (URDF-derived frames) are populated for our side. The `/scoring/tf` namespace carries ground-truth poses and is **off-limits**.

## Implication for our policy

- Cannot localize the port via `/tf` lookup at eval. Must use vision (autoencoder?) or another inference path.
- The board pose itself is unknown — but the cameras are wrist-mounted and the board is in view at the start.
- The 5 mm xy tolerance on partial-insertion scoring is generous; the search for the port can be guided by visual servoing rather than absolute pose.
