# Web UI Quick Start

## Development

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
  - Teams: `0..2` (`0=Rot`, `1=Blau`, `2=Violett/FFA`)
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
