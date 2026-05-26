# LaserOps Web App (Raspberry Pi Ready)

This web app reuses the BLE logic from `scripts/laserops.py`.
The browser only talks to the local HTTP API; BLE traffic is handled on the host
(typically a Raspberry Pi).

## Local Start

No frontend build or compile step is required.

```bash
pip install -r webapp/requirements.txt
python -m uvicorn webapp.backend.app:app --host 0.0.0.0 --port 8000
```

Open:

`http://<host-ip>:8000`

## Current Features

- Scan for LaserOps devices
- Connect / disconnect
- Startup sequence with configurable volume
- Set volume
- Write level/name indexes (index maps to payload byte `index + 1`)
- Set team/slot per blaster (slot `2..5`, team `0..1`)
- Local per-blaster player names (persisted in `webapp/backend/state/local_names.json`)
- Single-blaster game start
- Multiplayer start for connected blasters
- Status polling
- Manual session close
- Notification log view
- Live stream for all connected blasters (SSE)
- Round ranking and end-of-round statistics via multiplayer flow (`47`/`54`)

## API Notes

- Legacy `POST /api/stats/{address}` is disabled in safe mode
- `POST /api/game/start-multi` requires at least 2 connected blasters
- Multiplayer teams must be either:
  - red-vs-blue only (`0/1`)
  - or all-violet (`2`) for free-for-all
  - mixed violet with red/blue is blocked because hits are not counted reliably
- Some blaster profiles still require a manual reload press after start to confirm round activation

## Safety Mode (Enabled)

The backend enforces conservative safety limits:

- Only known/observed command families are allowed in BLE safe mode
- BLE writes are throttled (minimum spacing)
- Level is limited to `1..5`
- Name indexes are limited to `0..49`
- Team is limited to `0..2`
- Slot is limited to `2..5`
- Start command delay is limited to `0.00..0.30 s`
- Multiplayer start runs as an exclusive operation to avoid command collisions

Important: because this is reverse-engineered firmware behavior, absolute guarantees are
not possible. Safety mode reduces risk through strict protocol boundaries.

## Live Streaming

SSE endpoint:

- `GET /api/live/stream`

This allows live UI updates across multiple connected blasters without extra BLE polling.

## Raspberry Pi Service (systemd)

Example service file at `/etc/systemd/system/laserops-web.service`:

```ini
[Unit]
Description=LaserOps Web Control
After=network.target bluetooth.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Laser_0ps_bluetooth
ExecStart=/home/pi/Laser_0ps_bluetooth/.venv/bin/python -m uvicorn webapp.backend.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
```

Enable/start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable laserops-web
sudo systemctl start laserops-web
sudo systemctl status laserops-web
```
