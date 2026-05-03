# LaserOps BLE Protocol — Overview

This document summarises the Bluetooth Low Energy (BLE) GATT structure used by Hasbro NERF LaserOps Pro blasters.  All information was obtained by sniffing the official Android app and by active characteristic exploration.

---

## Device Advertisement

| Field               | Value                                    |
|---------------------|------------------------------------------|
| Complete Local Name | `LaserOps_Alpha` or `LaserOps_Delta`     |
| Manufacturer data   | `0x0218 <2-byte device serial>`          |
| Appearance          | 0x0180 (Generic Outdoor Sports Activity) |

Blasters advertise on all three primary BLE advertising channels (37, 38, 39) with a 100 ms interval while in *pairing* mode, and 500 ms once paired/idle.

---

## GATT Services

### 1. Device Information Service (standard)

UUID: `0000180a-0000-1000-8000-00805f9b34fb`

| Characteristic          | UUID (short) | Properties  | Description                |
|-------------------------|--------------|-------------|----------------------------|
| Manufacturer Name       | `0x2A29`     | Read        | `"Hasbro"`                 |
| Model Number            | `0x2A24`     | Read        | `"LaserOpsAlpha"` / `"LaserOpsDelta"` |
| Firmware Revision       | `0x2A26`     | Read        | e.g. `"1.2.0"`             |
| Software Revision       | `0x2A28`     | Read        | e.g. `"1.0.3"`             |

---

### 2. LaserOps Control Service (proprietary)

UUID: `0000aa00-0000-1000-8000-00805f9b34fb`

| Characteristic     | UUID (short) | Properties       | Description                          |
|--------------------|--------------|------------------|--------------------------------------|
| Command            | `0xAA01`     | Write            | Send control commands to the blaster |
| Status / Event     | `0xAA02`     | Notify           | Receive status updates and hit events|
| Player Config      | `0xAA03`     | Read / Write     | Player name, ID, and team            |
| Game Config        | `0xAA04`     | Read / Write     | Game mode, duration, lives, etc.     |

---

### 3. LaserOps Statistics Service (proprietary)

UUID: `0000bb00-0000-1000-8000-00805f9b34fb`

| Characteristic     | UUID (short) | Properties       | Description                          |
|--------------------|--------------|------------------|--------------------------------------|
| Statistics         | `0xBB01`     | Read / Notify    | End-of-game statistics blob          |
| History            | `0xBB02`     | Read             | Up to 10 previous game summaries     |

---

## Notification / CCCD Descriptors

All *Notify* characteristics must have their Client Characteristic Configuration Descriptor (CCCD, `0x2902`) written to `0x0100` before the blaster will push unsolicited updates.

---

## BLE Security

Blasters use *Just Works* pairing (no PIN required).  Once bonded, a random 128-bit session key is exchanged via the Command characteristic on each re-connection (see `packets.md` → `CMD_HELLO`).

---

## Connection Parameters

| Parameter            | Value          |
|----------------------|----------------|
| Connection interval  | 20–40 ms       |
| Slave latency        | 0              |
| Supervision timeout  | 4 s            |

---

## Notes

- The blaster disconnects automatically after **30 seconds** of inactivity.
- Firmware updates are delivered via a separate, undocumented OTA service (`0000fe00-…`); avoid writing to it unless you know what you are doing.
- All multi-byte integer fields are **little-endian** unless stated otherwise.

---

See [`packets.md`](packets.md) for the full command / event packet format reference.
