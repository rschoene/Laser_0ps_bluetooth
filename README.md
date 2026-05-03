# Laser_0ps_bluetooth

Reverse-engineering documentation and Python tooling for the **Hasbro NERF LaserOps** Bluetooth Low Energy (BLE) protocol, derived entirely from Android BLE HCI captures.

## Project Goal

Document the BLE protocol used by NERF LaserOps blasters and provide scripts to:

- **Scan** for LaserOps devices nearby
- **Assign** player level / name to a blaster
- **Send** game-start commands
- **Collect** end-of-game statistics

All protocol knowledge comes from BLE HCI snoop captures of the official Hasbro Android app (see `test_on_android/` for raw logs and analysis).

> **Note:** Confidence levels for protocol fields vary.  
> Fields marked *confirmed* appear consistently across multiple captures; fields marked *inferred* are consistent with observed traffic but their exact semantics are not yet proven.  
> Treat inferred fields with caution and verify against new captures before relying on them.

---

## Repository Layout

```
Laser_0ps_bluetooth/
├── README.md                    ← This file
├── LICENSE
├── protocol/
│   ├── README.md                ← ATT transport and message-type reference
│   └── packets.md               ← Payload formats with raw observed examples
├── scripts/
│   ├── requirements.txt         ← Python dependency (bleak)
│   ├── laserops.py              ← Core BLE library (handles, message builders/parsers)
│   ├── scan.py                  ← Discover nearby LaserOps blasters
│   ├── assign_device.py         ← Write level / name config to a blaster
│   ├── start_game.py            ← Send game-start command sequence
│   └── collect_stats.py         ← Retrieve end-of-game statistics
└── test_on_android/
    ├── test_definition.md       ← How captures were collected
    ├── test_1/ … test_7/        ← Per-test notes and filtered HCI logs
    └── upgrades_powerups.md
```

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

### 1 — Scan for blasters

```bash
python scan.py
```

### 2 — Write level / name config to a blaster

```bash
# Level 3, name parts at app-indices 17 and 19
python assign_device.py --address E4:FE:7C:AA:11:22 --level 3 --name-a 17 --name-b 19
```

### 3 — Send game-start command sequence

```bash
python start_game.py --address E4:FE:7C:AA:11:22
```

### 4 — Collect end-of-game statistics

```bash
python collect_stats.py --address E4:FE:7C:AA:11:22 --output results.json
```

---

## Protocol Overview

See [`protocol/README.md`](protocol/README.md) for the ATT transport details and a summary of all known message types, and [`protocol/packets.md`](protocol/packets.md) for payload formats with raw observed examples.

---

## Contributing

Contributions (additional HCI captures, corrections, clarifications) are welcome.  
Please open an issue or a pull request.

---

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE).
