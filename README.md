# Laser_0ps_bluetooth

Reverse-engineering and Python/web tooling for **Hasbro NERF LaserOps** over Bluetooth Low Energy (BLE).

The main goal is safe and repeatable multi-blaster operation through a local server
(typically a Raspberry Pi as the central host).

## Credits

This repository is based on foundational work by:

- **Robert Schone (`rschoene`)**
- Project: https://github.com/rschoene/Laser_0ps_bluetooth

Thanks for the original reverse-engineering work and protocol groundwork.

## Project Goals

- Document and validate the BLE protocol in practical usage
- Manage multiple blasters from a browser UI
- Start and control rounds with explicit slot/team assignment
- Run reliably as a long-lived local service (Raspberry Pi target)

## Repository Layout

```text
Laser_0ps_bluetooth/
  README.md
  scripts/                 # BLE core and CLI tooling
  webapp/                  # FastAPI backend + web UI
  protocol/                # Human-readable protocol documentation
  definition_protocol/     # Machine-readable protocol definition
  test_on_android/         # Capture notes and reverse-engineering evidence
```

## Quick Start (Development)

No frontend build step is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r webapp/requirements.txt
python -m uvicorn webapp.backend.app:app --host 0.0.0.0 --port 8000
```

Open:

`http://<HOST-IP>:8000`

## Raspberry Pi Installation (Recommended)

### 1) Base packages

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip bluetooth bluez
```

Ensure Bluetooth service is running:

```bash
sudo systemctl enable bluetooth
sudo systemctl start bluetooth
sudo systemctl status bluetooth
```

### 2) Copy project to the Pi

Recommended path:

`/home/pi/Laser_0ps_bluetooth`

Use either `git clone` or FTP/SFTP upload.

### 3) Python environment

```bash
cd /home/pi/Laser_0ps_bluetooth
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r webapp/requirements.txt
```

### 4) Manual server test

```bash
cd /home/pi/Laser_0ps_bluetooth
source .venv/bin/activate
python -m uvicorn webapp.backend.app:app --host 0.0.0.0 --port 8000
```

Open:

`http://<PI-IP>:8000`

### 5) Run as systemd service

Create `/etc/systemd/system/laserops-web.service`:

```ini
[Unit]
Description=LaserOps Web Control
After=network.target bluetooth.target
Wants=bluetooth.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/Laser_0ps_bluetooth
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/pi/Laser_0ps_bluetooth/.venv/bin/python -m uvicorn webapp.backend.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable laserops-web
sudo systemctl start laserops-web
sudo systemctl status laserops-web
```

Live logs:

```bash
journalctl -u laserops-web -f
```

## Operational Notes

- Team/slot constraints are currently limited to:
  - Slots: `2..5`
  - Teams: `0..1`
- Multiplayer start requires at least **2 connected blasters**
- Some blaster/firmware profiles still need a **manual reload press** after start to confirm round activation
- Legacy `/api/stats/{address}` is disabled in safe mode

## Update Workflow

```bash
cd /home/pi/Laser_0ps_bluetooth
source .venv/bin/activate
pip install -r webapp/requirements.txt
sudo systemctl restart laserops-web
```

## Safety Notice (BLE Reverse Engineering)

All BLE command semantics are based on reverse engineering, not official vendor protocol documentation.
Safety guards are implemented (command allow-list, strict bounds, write throttling), but absolute guarantees
for every firmware behavior are technically not possible.

## Documentation

- Web app details: `webapp/README.md`
- Protocol details: `protocol/README.md` and `protocol/packets.md`
- Android capture workflow: `test_on_android/test_definition.md`

## License

GNU General Public License v3.0, see [LICENSE](LICENSE).
