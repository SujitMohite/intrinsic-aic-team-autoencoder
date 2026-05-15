# Qualification Trials

Source: [`docs/qualification_phase.md`](../../docs/qualification_phase.md), [`aic_engine/config/sample_config.yaml`](../../aic_engine/config/sample_config.yaml).

> The exact number and sequence may shift at eval. They will always be some combination of SFP→NIC and SC→port. Plan to **handle 5 NIC rails**, not just the 2 in the published config.

## Trial 1 & 2 — SFP convergence under NIC randomization

- **Cable in gripper:** `sfp_sc_cable`, gripped by the **SFP module** end.
- **Free end:** the SC plug, unconnected.
- **Target:** insert SFP module into `SFP_PORT_0` or `SFP_PORT_1` on a **NIC card** mounted on one of `nic_rail_0` … `nic_rail_4`.
- **What varies between trial 1 and trial 2:**
  - Task board pose (x, y, z, yaw).
  - Which NIC rail holds the card.
  - Translation along that rail and yaw offset of the card.
- **What `aic_engine` tells us via the Task message:** `port_name` (e.g. `sfp_port_0`) and `target_module_name` (e.g. `nic_card_0`).
- **Initial robot pose:** Close enough that the port is in camera view (a few cm). See `sample_config.yaml:327-335` for home joints.

## Trial 3 — SC generalization

- **Cable in gripper:** same `sfp_sc_cable`, but now gripped by the **SC plug** end.
- **Free end:** SFP module.
- **Target:** insert SC plug into `SC_PORT_0` (`sc_rail_0`) or `SC_PORT_1` (`sc_rail_1`), as specified in the Task.
- **Other variation:** Each SC port has a random translation along its rail.

## Grasp pose noise (important)

The grasp between plug and `gripper/tcp` is **not** identical every trial:
- Nominal SFP grasp: `x=0.0, y=0.015385, z=0.04245, roll=0.4432, pitch=-0.4838, yaw=1.3303` (sample_config).
- Nominal SC grasp:  `x=0.0, y=0.015385, z=0.04045, roll=0.4432, pitch=-0.4838, yaw=1.3303`.
- **Expected deviation at eval:** ~2 mm in translation, ~0.04 rad in rotation.

Our policy must be **grasp-pose robust** at this magnitude. Pure analytic IK from `tcp → plug → port` will fail without visual or force feedback.

## Task message contents

Per [`aic_interfaces/aic_task_interfaces/msg/Task.msg`](../../aic_interfaces/aic_task_interfaces/msg/Task.msg):

```
string id
string cable_type        # "sfp_sc_cable"
string cable_name        # "sfp_sc"
string plug_type         # "sfp" | "sc"
string plug_name         # "sfp_module" | "sc_plug"
string port_type         # "sfp" | "sc"
string port_name         # "sfp_port_0" / "sfp_port_1" / "sc_port_0" / "sc_port_1"
string target_module_name  # "nic_card_0" .. "nic_card_4" | (sc port has no parent module)
uint64 time_limit        # seconds, sim time. sample config: 180.
```

## Per-trial time budget

`time_limit = 180 s` of sim time per trial (sample_config). The 12-point duration bonus saturates at ≤ 5 s and goes to 0 at ≥ 60 s — so **fast** is rewarded even though the cap is 180 s.

## Rail and pose ranges (sample_config)

- NIC rail translation: `-0.0215` to `+0.0234` m (range 0.045 m).
- SC rail translation: `-0.06` to `+0.055` m (range 0.115 m).
- Mount rails: `-0.09425` to `+0.09425` m (range 0.189 m).

NIC card yaw offset is randomized but bounds aren't in the config — assume ±10°.

## What this means for our policy

- **One policy, two plug families.** It must look at the Task to know which port to aim for, and the geometry / appearance of the SFP vs SC tip and port differ.
- **Search behaviour is OK** but every second beyond the optimal path bleeds points.
- **No assumptions about NIC index.** Don't write `if target_module_name == "nic_card_0"`. Use the Task fields and TF (or learned perception) to localize.
