# Laser_0ps_bluetooth

Reverse-engineering documentation and Python tooling for the **Hasbro NERF LaserOps** Bluetooth Low Energy (BLE) protocol, derived entirely from Android BLE HCI captures.

## Contributing

Contributions (additional HCI captures, corrections, clarifications) are welcome, especially for Hasbro Nerf LaserOps Pro DeltaBurst devices, to which I do not have access.
Please open an issue or a pull request.
If you provide an HCI capture, it would be great if you'd document what you did (number of devices, game mode and setup, estimation or detailed description of statistics and so on).
Check `test_on_android/test_definition.md` on how to capture HCI protocols on Android.

---

## Project Goals

- Document the observed BLE protocol between app and blaster(s).
- Keep test runs reproducible and comparable across sessions.
- Provide machine-readable protocol definitions usable in Python.
- Provide Python scripts to scan, configure, and interact with blasters.

All protocol knowledge comes from BLE HCI snoop captures of the official Hasbro Android app (see `test_on_android/` for raw logs and analysis).

> **Note:** Confidence levels for protocol fields vary.  
> Fields marked *confirmed* appear consistently across multiple captures; fields marked *inferred* are consistent with observed traffic but their exact semantics are not yet proven.  
> Treat inferred fields with caution and verify against new captures before relying on them.

---

## Repository Layout

```
Laser_0ps_bluetooth/
├── README.md                         ← This file
├── LICENSE
├── definition_protocol/
│   ├── protocol_definition.json      ← Machine-readable protocol model
│   ├── example_ble_protocol_client.py← BLE scanner/client example using Bleak
│   └── README.md                     ← Usage instructions for the Python client
├── protocol/
│   ├── README.md                     ← ATT transport and message-type reference
│   └── packets.md                    ← Payload formats with raw observed examples
├── scripts/
│   ├── requirements.txt              ← Python dependency (bleak)
│   ├── laserops.py                   ← Core BLE library (handles, message builders/parsers)
│   ├── scan.py                       ← Discover nearby LaserOps blasters
│   ├── assign_device.py              ← Write level / name config to a blaster
│   ├── start_game.py                 ← Send game-start command sequence
│   └── collect_stats.py              ← Retrieve end-of-game statistics
└── test_on_android/
    ├── test_definition.md            ← Test plan definitions and capture instructions
    ├── test_1/ … test_7/             ← Per-test notes and filtered HCI logs
    └── upgrades_powerups.md
```

---

## Current Protocol Status

The protocol is reverse-engineered and still evolving.

High-confidence items include:

- Transport direction and handles:
  - host writes typically on `0x0026`
  - gun notifications typically on `0x0023`
- Startup exchange (`35` query, `35...` snapshot, initial `5bxx` volume set).
- Config/state writes (`36...`) and persistent level byte behavior.
- Gameplay event families (`49`, `52` + `31xx`, `32xx`).
- End-stat flow (`5a3f...`, `30013f...`, `3e0100`, `42`).

See [`protocol/README.md`](protocol/README.md) for the ATT transport details and a summary of all known message types, [`protocol/packets.md`](protocol/packets.md) for payload formats with raw observed examples, and `test_on_android/test_1/traffic_definition.md` for detailed byte-level notes and confidence annotations.

---

## Quick Start

### Prerequisites

- Python 3.8 or newer
- A Bluetooth 4.0+ adapter (Linux: BlueZ ≥ 5.43 recommended)

### Install dependencies

```bash
cd scripts
pip install -r requirements.txt
```

### Scan for blasters

```bash
python scan.py
```

### Write level / name config to a blaster

```bash
# Level 3, name parts at observed byte values 0x17 and 0x19
python assign_device.py --address E4:FE:7C:AA:11:22 --level 3 --name-a 23 --name-b 25
```

### Send game-start command sequence

```bash
python start_game.py --address E4:FE:7C:AA:11:22
```

### Collect end-of-game statistics

```bash
python collect_stats.py --address E4:FE:7C:AA:11:22 --output results.json
```

### Run the low-level BLE example client

```bash
python definition_protocol/example_ble_protocol_client.py \
    --address <gun_0_address> \
    --pair \
    --send-startup \
    --startup-volume 0 \
    --listen-seconds 60
```

---

## Data Privacy / Sanitization

This repository has been sanitized for public sharing:

- Real device MAC addresses were replaced with stable fake values in all `filtered_.log` files.
- Replacement map is documented in `test_on_android/devices.md` (git-ignored).
- Raw Bluetooth snoop files (`btsnoop_hci.log`) are git-ignored.

Current sanitized mapping labels used in docs and notes:

- `phone_host`
- `gun_0`
- `gun_1`
- `gun_2`
- `gun_3`

---

## Limitations

- Some field meanings are inferred and may change with new captures.
- App/blaster firmware changes can shift payload families (for example `0x0a`-series to `0x0d`/`0x0e`-series after level 4+).

---

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE).
