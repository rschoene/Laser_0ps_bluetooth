# Laser_0ps_bluetooth

Reverse-engineering documentation and tooling for the **Hasbro NERF LaserOps** Bluetooth Low Energy (BLE) protocol.

## Project Goal

This project documents the BLE protocol used by the NERF LaserOps Pro blasters (AlphaPoint / Delta Burst) and provides Python scripts that allow you to:

- **Scan** for LaserOps devices nearby
- **Assign** player names, IDs, and team colours to blasters
- **Start / stop** game sessions from a host machine (no phone required)
- **Collect statistics** (shots fired, hits received, accuracy, …) at the end of a game

All findings are derived from passive BLE sniffing of the official Hasbro Android app together with active probing of GATT characteristics.

---

## Repository Layout

```
Laser_0ps_bluetooth/
├── README.md               ← This file
├── LICENSE
├── protocol/
│   ├── README.md           ← BLE service / characteristic overview
│   └── packets.md          ← Detailed packet-format reference
└── scripts/
    ├── requirements.txt    ← Python dependencies (bleak, …)
    ├── laserops.py         ← Core BLE device library
    ├── scan.py             ← Discover nearby LaserOps blasters
    ├── assign_device.py    ← Set player name / ID / team on a blaster
    ├── start_game.py       ← Start (and stop) a game session
    └── collect_stats.py    ← Retrieve end-of-game statistics
```

---

## Quick Start

### Prerequisites

- Python 3.8 or newer
- A Bluetooth 4.0+ adapter (Linux: BlueZ ≥ 5.43 recommended)
- NERF LaserOps Pro blaster(s) in *pairing* mode (hold the power button until the LED flashes rapidly)

### Install dependencies

```bash
cd scripts
pip install -r requirements.txt
```

### 1 — Scan for blasters

```bash
python scan.py
```

Sample output:

```
Scanning for LaserOps devices (10 s) …
  [1]  LaserOps_Alpha   E4:FE:7C:AA:11:22   RSSI -62 dBm
  [2]  LaserOps_Delta   E4:FE:7C:BB:33:44   RSSI -71 dBm
Found 2 device(s).
```

### 2 — Assign player info

```bash
python assign_device.py --address E4:FE:7C:AA:11:22 \
                        --name "Player1" \
                        --player-id 1 \
                        --team 0
```

### 3 — Start a game

```bash
# Start a 10-minute team deathmatch
python start_game.py --addresses E4:FE:7C:AA:11:22 E4:FE:7C:BB:33:44 \
                     --mode team_deathmatch \
                     --duration 600
```

### 4 — Collect statistics

```bash
python collect_stats.py --addresses E4:FE:7C:AA:11:22 E4:FE:7C:BB:33:44 \
                        --output results.json
```

---

## Protocol Overview

See [`protocol/README.md`](protocol/README.md) for service / characteristic UUIDs and [`protocol/packets.md`](protocol/packets.md) for the full packet-format reference.

---

## Contributing

Contributions (additional packet captures, corrections, new scripts) are very welcome.  
Please open an issue or a pull request.

---

## License

This project is licensed under the GNU General Public License v3.0 — see [LICENSE](LICENSE) for details.
