# Asset Catalog

Source: [`aic_assets/models/`](../../aic_assets/models/). Each subdirectory is an SDF model.

## Cables (in gripper at start)

| Asset | What it is | Used in |
| --- | --- | --- |
| `sfp_sc_cable` | One cable with **SFP module on one end, SC plug on the other** — the cable for all 3 qualification trials | Trials 1, 2 (SFP grasped) and trial 3 (SC grasped) |
| `sfp_sc_cable_reversed` | Same, mirrored orientation | Alt config |
| `lc_cable` | Cable terminating in LC plugs | Not in qualification |
| `lc_sc_cable` | LC ↔ SC | Not in qualification |
| `sc_cable` | SC-only | Not in qualification |
| `cable_base_c_rotated`, `cable_base_c_rotated_reversed` | Generic flexible-cable bases | Internal |

## Plugs (cable ends)

| Asset | Connector | When seen |
| --- | --- | --- |
| `SFP Module` | SFP transceiver (rectangular metal cage) | Trials 1, 2 in gripper |
| `SC Plug` | SC fiber plug (square latch) | Trial 3 in gripper |
| `LC Plug` | LC fiber plug (small, dual ferrules) | Not in qualification |

## Ports (insertion targets)

| Asset | On which module | Trial |
| --- | --- | --- |
| `SFP Port` (named `sfp_port_0`, `sfp_port_1`) | Each NIC card has 2 SFP ports | Trials 1, 2 |
| `SC Port` (named `sc_port_0`, `sc_port_1`) | Mounted directly on `sc_rail_0/1` | Trial 3 |

## Carriers

| Asset | Role |
| --- | --- |
| `NIC Card` | Holds 2 SFP ports; goes on a `nic_rail_*` |
| `NIC Card Mount` | The rail slot |
| `SC Mount` | Mount for SC ports |
| `SC Port` (mount variant) | Standalone SC port + mount |
| `LC Mount`, `SFP Mount` | Pick-zone holders (not used at eval) |

## Robot & sensors

| Asset | Role |
| --- | --- |
| `Robotiq Hand-E` | Gripper |
| `Axia80 M20` | ATI F/T sensor at the wrist |
| `Basler Camera` | One of three wrist cameras |
| `Camera Mount` | Holds the 3 cameras |

## Environment

| Asset | Role |
| --- | --- |
| `Task Board Base` | The flat workboard plate |
| `Enclosure` | Floor + posts + ceiling (off-limit) |
| `Enclosure Walls` | Acrylic side panels (off-limit) |
| `Floor` | Ground plane |

## Visual / cosmetic only

(None major — every asset above has functional meaning in the simulator.)

## Implication for our perception

- **The SFP module and SC plug look very different** in any wrist camera image. Useful inductive bias for the autoencoder / classifier head.
- **NIC cards are visually similar across `nic_card_0…4`** — the only cue is which rail they're on (and the Task tells us which to aim for, by name).
- **SC ports are large and high-contrast** — should be easy to localize visually.
- Lighting comes from the GI plugin; if we turn GI off (CPU fallback), visual policies will see a flatter scene.
