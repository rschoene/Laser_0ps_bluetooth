# LaserOps BLE Protocol — Packet Format Reference

All packets are exchanged via the **Command** (`0xAA01`) and **Status/Event** (`0xAA02`) characteristics of the LaserOps Control Service.  All multi-byte integers are **little-endian**.

---

## General Packet Structure

```
 0         1         2         3 … N-2     N-1
┌─────────┬─────────┬─────────┬──────────┬─────────┐
│  MAGIC  │  OPCODE │  LENGTH │ PAYLOAD  │ CHECKSUM│
│  0x4C   │  1 byte │  1 byte │ N-3 bytes│  1 byte │
└─────────┴─────────┴─────────┴──────────┴─────────┘
```

| Field    | Size   | Description                                                         |
|----------|--------|---------------------------------------------------------------------|
| MAGIC    | 1 byte | Always `0x4C` (`'L'` for LaserOps)                                 |
| OPCODE   | 1 byte | Command / event identifier (see tables below)                       |
| LENGTH   | 1 byte | Number of bytes in PAYLOAD (0–252)                                  |
| PAYLOAD  | N bytes| Opcode-specific data                                                |
| CHECKSUM | 1 byte | XOR of all preceding bytes (MAGIC ^ OPCODE ^ LENGTH ^ all PAYLOAD) |

---

## Command Opcodes (host → blaster, written to `0xAA01`)

### `CMD_HELLO` — `0x01`

Sent immediately after connecting.  Exchanges a session nonce used for lightweight integrity checking.

| Offset | Size | Field        | Description                        |
|--------|------|--------------|------------------------------------|
| 0      | 4    | host_nonce   | Random 32-bit value chosen by host |

Response: `EVT_HELLO` (see below).

---

### `CMD_SET_PLAYER` — `0x10`

Configure player identity on the blaster.

| Offset | Size | Field       | Description                                    |
|--------|------|-------------|------------------------------------------------|
| 0      | 1    | player_id   | 1–8 (unique per game)                          |
| 1      | 1    | team_id     | 0 = free-for-all, 1 = red team, 2 = blue team  |
| 2      | 1    | name_len    | Length of UTF-8 name string (max 12 bytes)     |
| 3      | 1–12 | name        | Player name (UTF-8, **not** NUL-terminated)    |

---

### `CMD_GET_PLAYER` — `0x11`

Request current player configuration.  No payload.  Response: `EVT_PLAYER_CFG`.

---

### `CMD_SET_GAME` — `0x20`

Configure game parameters.

| Offset | Size | Field        | Description                                              |
|--------|------|--------------|----------------------------------------------------------|
| 0      | 1    | game_mode    | 0=FFA, 1=Team Deathmatch, 2=Capture the Flag, 3=Survival |
| 1      | 2    | duration_s   | Game duration in seconds (0 = unlimited)                  |
| 3      | 1    | lives        | Lives per player (0 = unlimited)                         |
| 4      | 1    | respawn_s    | Respawn delay in seconds                                 |
| 5      | 1    | friendly_fire| 0 = disabled, 1 = enabled                                |

---

### `CMD_START_GAME` — `0x21`

Start the configured game.  All connected blasters must have received `CMD_SET_PLAYER` and `CMD_SET_GAME` first.  No payload.

---

### `CMD_STOP_GAME` — `0x22`

Immediately end the current game.  No payload.  Triggers `EVT_GAME_END` on all blasters.

---

### `CMD_GET_STATS` — `0x30`

Request end-of-game statistics.  No payload.  Response: `EVT_STATS`.

---

### `CMD_RESET` — `0xF0`

Soft-reset the blaster (returns to idle/advertising state).  No payload.

---

## Event Opcodes (blaster → host, received on `0xAA02` notifications)

### `EVT_HELLO` — `0x81`

Response to `CMD_HELLO`.

| Offset | Size | Field          | Description                                            |
|--------|------|----------------|--------------------------------------------------------|
| 0      | 4    | device_nonce   | Random 32-bit value chosen by the blaster              |
| 4      | 2    | firmware_ver   | BCD-encoded firmware version (e.g. `0x0120` = v1.2.0) |
| 6      | 1    | battery_pct    | Battery level 0–100                                    |

---

### `EVT_PLAYER_CFG` — `0x91`

Response to `CMD_GET_PLAYER`; same layout as `CMD_SET_PLAYER` payload.

---

### `EVT_HIT` — `0xA0`

Sent whenever this blaster is hit.

| Offset | Size | Field        | Description                                      |
|--------|------|--------------|--------------------------------------------------|
| 0      | 1    | shooter_id   | player_id of the shooter (0 if unknown)          |
| 1      | 1    | shooter_team | team_id of the shooter                           |
| 2      | 1    | damage       | Damage points (typically 1)                      |
| 3      | 1    | health_left  | Remaining health after this hit (0 = eliminated) |

---

### `EVT_SHOT_FIRED` — `0xA1`

Sent whenever the trigger is pulled.

| Offset | Size | Field      | Description                           |
|--------|------|------------|---------------------------------------|
| 0      | 1    | shots_left | Remaining shots in current clip       |

---

### `EVT_ELIMINATED` — `0xA2`

Sent when the player is eliminated (health reaches 0).  No payload.

---

### `EVT_RESPAWN` — `0xA3`

Sent when the player respawns after elimination.  No payload.

---

### `EVT_GAME_END` — `0xB0`

Sent when the game ends (time expired, `CMD_STOP_GAME` received, or last player standing).

| Offset | Size | Field      | Description                    |
|--------|------|------------|--------------------------------|
| 0      | 1    | reason     | 0=time_up, 1=stopped, 2=winner |
| 1      | 1    | winner_id  | player_id of winner (FFA only) |
| 2      | 1    | winner_team| team_id of winning team        |

---

### `EVT_STATS` — `0xC0`

Response to `CMD_GET_STATS`.

| Offset | Size | Field          | Description                          |
|--------|------|----------------|--------------------------------------|
| 0      | 1    | player_id      | This player's ID                     |
| 1      | 2    | shots_fired    | Total shots fired during the game    |
| 3      | 2    | hits_received  | Times this player was hit            |
| 5      | 2    | hits_scored    | Confirmed hits on other players      |
| 7      | 2    | eliminations   | Number of players this player killed |
| 9      | 2    | deaths         | Number of times this player died     |
| 11     | 2    | game_duration_s| Actual game duration in seconds      |
| 13     | 1    | accuracy_pct   | shots that hit / shots fired × 100   |

---

## Checksum Calculation

```python
def checksum(packet_without_checksum: bytes) -> int:
    result = 0
    for byte in packet_without_checksum:
        result ^= byte
    return result
```

---

## Example: Start a 5-minute FFA game with Player 1

```
# CMD_SET_PLAYER  player_id=1, team=0, name="Player1"
4C 10 09  01 00 07 50 6C 61 79 65 72 31  CS

# CMD_SET_GAME  mode=FFA, duration=300s, lives=3, respawn=5s, no friendly_fire
4C 20 06  00 2C 01 03 05 00  CS

# CMD_START_GAME
4C 21 00  CS
```

(Replace `CS` with the XOR checksum of all preceding bytes in each packet.)
