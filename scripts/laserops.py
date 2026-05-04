"""
laserops.py — Core BLE library for NERF LaserOps blasters.

Protocol knowledge is derived exclusively from Android BLE HCI captures.
All semantics marked "inferred" are consistent with observed traffic but
not yet proven; treat them as tentative.

Transport:
  - Write to ATT handle 0x0026 (Write Command, ATT opcode 0x52)
  - Receive notifications from ATT handle 0x0023 (Handle Value Notification)
  - One-time setup write on ATT handle 0x0024 (Write Request) to enable notifications
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable, Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

# ---------------------------------------------------------------------------
# BLE identity constants (confirmed from HCI advertisement captures)
# ---------------------------------------------------------------------------

# All LaserOps blasters advertise this exact device name.
DEVICE_NAME = "NerfV"

# 128-bit primary service UUID (advertised in AD type 0x07).
# Use this for reliable filtering — the device name alone may not be unique.
SERVICE_UUID     = "073e1435-85d1-455c-97cd-0b8262f20eac"

# Characteristic UUIDs (confirmed from GATT service discovery)
NOTIFY_CHAR_UUID = "073e1382-85d1-455c-97cd-0b8262f20eac"  # Notify + Read
WRITE_CHAR_UUID  = "073e1383-85d1-455c-97cd-0b8262f20eac"  # Write Without Response + Read

# ---------------------------------------------------------------------------
# ATT handle constants (confirmed from captures)
# ---------------------------------------------------------------------------

NOTIFY_HANDLE = 0x0023  # gun → host notifications
WRITE_HANDLE  = 0x0026  # host → gun write commands
SETUP_HANDLE  = 0x0024  # one-time setup write (enables notifications)

# ---------------------------------------------------------------------------
# Message ID bytes (leading byte of each payload family)
# ---------------------------------------------------------------------------

# Startup exchange (confirmed)
MSG_STARTUP_QUERY    = 0x35   # host → gun: 1 byte
MSG_STARTUP_SNAPSHOT = 0x35   # gun → host: 13 bytes

# Config write (confirmed structure)
MSG_CONFIG_WRITE     = 0x36   # host → gun: 13 bytes
MSG_APPLY_COMMIT     = 0x57   # host → gun: 1 byte (inferred meaning)

# Volume control (confirmed)
MSG_VOLUME_SET       = 0x5B   # host → gun: 2 bytes, XX = 0x00–0x1f

# Status poll/reply (high confidence)
MSG_STATUS_POLL      = 0x51   # host → gun: 1 byte
MSG_STATUS_REPLY     = 0x51   # gun → host: 3 bytes

# Gameplay events (gun → host, confirmed)
MSG_TRIGGER          = 0x49   # 1 byte
MSG_RELOAD_A         = 0x52   # 1 byte, paired with reload_B ~0.5 s later
MSG_RELOAD_B_OLD     = 0x31   # 2 bytes: 31 0a (older mode)
MSG_RELOAD_B_NEW     = 0x31   # 2 bytes: 31 0d (newer/level-5 mode)
MSG_AMMO_STATE       = 0x32   # variable, per-shot counter update

# In-game control (host → gun, medium confidence)
MSG_GAME_CTRL        = 0x37   # 4 bytes

# End-of-game stats (inferred semantics)
MSG_STAT_REQUEST     = 0x5A   # host → gun: 6 bytes, prefix 5a3f01
MSG_STAT_COUNTER     = 0x30   # gun → host: 5 bytes, prefix 30013f
MSG_STAT_TERMINAL    = 0x3E   # gun → host: 3e0100

# Session close (low-medium confidence)
MSG_SESSION_CLOSE    = 0x42   # host → gun: 1 byte

# ---------------------------------------------------------------------------
# Volume constants (confirmed)
# ---------------------------------------------------------------------------

VOLUME_MIN = 0x00  # mute
VOLUME_MAX = 0x1F  # 31 decimal

# ---------------------------------------------------------------------------
# Data classes for decoded gun→host messages
# ---------------------------------------------------------------------------

@dataclass
class StartupSnapshot:
    """
    Decoded gun startup snapshot (message id 0x35, 13 bytes).

    Fields confirmed: raw bytes 8–10 contain level + two name-part bytes.
    Exact field names are inferred.
    """
    level: int       # byte 8  — persistent gun level (high confidence)
    name_a: int      # byte 9  — name part A (inferred)
    name_b: int      # byte 10 — name part B (inferred)
    raw: bytes       # full 13-byte payload for reference


@dataclass
class StatusReply:
    """Gun status reply (message id 0x51, 3 bytes).  Semantics inferred."""
    status_word: int   # bytes 1–2 as big-endian uint16 (drifts over time)
    raw: bytes


@dataclass
class StatCounterReply:
    """End-of-game stat counter (prefix 30013f, 5 bytes).  Semantics inferred."""
    stat_type: int   # byte 3 — matches the TT byte from the request
    counter: int     # byte 4 — descends to 00


# ---------------------------------------------------------------------------
# Message decoders
# ---------------------------------------------------------------------------

def decode_startup_snapshot(payload: bytes) -> Optional[StartupSnapshot]:
    """
    Decode a gun→host notification as a startup snapshot if it matches.

    Returns None if the payload does not have the expected 13-byte structure.
    """
    if len(payload) != 13 or payload[0] != MSG_STARTUP_SNAPSHOT:
        return None
    return StartupSnapshot(
        level=payload[8],
        name_a=payload[9],
        name_b=payload[10],
        raw=bytes(payload),
    )


def decode_status_reply(payload: bytes) -> Optional[StatusReply]:
    """Decode a 3-byte status reply notification."""
    if len(payload) != 3 or payload[0] != MSG_STATUS_REPLY:
        return None
    status_word = (payload[1] << 8) | payload[2]
    return StatusReply(status_word=status_word, raw=bytes(payload))


def decode_stat_counter(payload: bytes) -> Optional[StatCounterReply]:
    """Decode a 5-byte end-of-game stat counter notification (prefix 30 01 3f)."""
    if len(payload) != 5 or payload[:3] != bytes([0x30, 0x01, 0x3F]):
        return None
    return StatCounterReply(stat_type=payload[3], counter=payload[4])


def decode_notification(payload: bytes) -> str:
    """Human-readable decoding of any known gun→host notification payload."""
    h = payload.hex()

    snapshot = decode_startup_snapshot(payload)
    if snapshot is not None:
        return (
            f"startup_snapshot level={snapshot.level} "
            f"name_parts=(0x{snapshot.name_a:02x}, 0x{snapshot.name_b:02x}) "
            f"raw={h}"
        )

    status = decode_status_reply(payload)
    if status is not None:
        return f"status_reply 0x{status.status_word:04x} raw={h}"

    if h == "49":
        return "trigger_event"

    if h == "52":
        return "reload_marker_a"

    if h in ("310a", "310d"):
        return f"reload_marker_b variant=0x{payload[1]:02x} raw={h}"

    if payload[0:1] == b"\x32" and len(payload) >= 2:
        return f"ammo_state family=0x{payload[1]:02x} counter=0x{payload[-1]:02x} raw={h}"

    stat = decode_stat_counter(payload)
    if stat is not None:
        return f"stat_counter type=0x{stat.stat_type:02x} value=0x{stat.counter:02x} raw={h}"

    if h == "3e0100":
        return "stat_terminal (end-of-game stats complete)"

    return f"unknown raw={h}"


# ---------------------------------------------------------------------------
# Command builders
# ---------------------------------------------------------------------------

def build_startup_query() -> bytes:
    """Single-byte startup query sent to the gun at session start."""
    return bytes([MSG_STARTUP_QUERY])


def build_config_write(level: int, name_a: int, name_b: int) -> bytes:
    """
    Build a 13-byte config write payload (form A, host → gun).

    Observed in Test 1 when assigning level and name parts to guns.
    ``name_a`` and ``name_b`` are the raw byte values for bytes 9 and 10
    of the payload.  Based on captures, these appear to be (app_name_index + 1)
    for each of the two name words, but this relationship is inferred.

    Returns form A: 36 00 0a 02 02 03 00 0a LL NN MM 00 04
    """
    return bytes([
        MSG_CONFIG_WRITE, 0x00, 0x0A, 0x02, 0x02,
        0x03, 0x00, 0x0A,
        level & 0xFF, name_a & 0xFF, name_b & 0xFF,
        0x00, 0x04,
    ])


def build_apply_commit() -> bytes:
    """Single-byte apply/commit command (inferred meaning)."""
    return bytes([MSG_APPLY_COMMIT])


def build_volume_set(volume: int) -> bytes:
    """
    Build a 2-byte volume-set command.

    ``volume`` must be 0 (mute) to 31 (max).  Values outside this range
    are clamped.  Confirmed by Test 4 sweep data.
    """
    v = max(VOLUME_MIN, min(VOLUME_MAX, volume))
    return bytes([MSG_VOLUME_SET, v])


def build_status_poll() -> bytes:
    """Single-byte periodic status poll."""
    return bytes([MSG_STATUS_POLL])


def build_stat_request(stat_type: int) -> bytes:
    """
    Build a 6-byte end-of-game stat request.

    Observed ``stat_type`` values from captures: 0x01, 0x02, 0x06.
    Semantics of each type are inferred.
    """
    return bytes([0x5A, 0x3F, 0x01, stat_type & 0xFF, 0x00, 0x00])


def build_session_close() -> bytes:
    """Single-byte session close command (low-medium confidence)."""
    return bytes([MSG_SESSION_CLOSE])


# ---------------------------------------------------------------------------
# Handle resolver (mirrors the approach in definition_protocol/example_ble_protocol_client.py)
# ---------------------------------------------------------------------------

def find_char_by_handle(client: BleakClient, handle: int):
    """Return the GATT characteristic whose ATT handle matches ``handle``."""
    if client.services is None:
        return None
    for service in client.services:
        for char in service.characteristics:
            if char.handle == handle:
                return char
    return None


# ---------------------------------------------------------------------------
# High-level device class
# ---------------------------------------------------------------------------

NotificationCallback = Callable[[bytes], None]


class LaserOpsDevice:
    """
    Async context manager representing a BLE connection to a LaserOps blaster.

    The protocol uses two ATT handles:
      - 0x0023 for gun→host notifications
      - 0x0026 for host→gun write commands

    Usage::

        async with LaserOpsDevice(ble_device) as gun:
            snapshot = await gun.startup()
            print(f"Level: {snapshot.level}")
            await gun.set_volume(0)
    """

    def __init__(
        self,
        device: BLEDevice,
        notification_callback: Optional[NotificationCallback] = None,
    ) -> None:
        self._device = device
        self._client = BleakClient(device)
        self._notification_callback = notification_callback
        self._pending: dict[bytes, asyncio.Future] = {}
        self._notify_char = None
        self._write_char = None

    # ---- context manager --------------------------------------------------

    async def __aenter__(self) -> "LaserOpsDevice":
        await self._client.connect()

        self._notify_char = find_char_by_handle(self._client, NOTIFY_HANDLE)
        self._write_char  = find_char_by_handle(self._client, WRITE_HANDLE)

        if self._notify_char is None:
            raise RuntimeError(
                f"Notify characteristic (handle 0x{NOTIFY_HANDLE:04x}) not found"
            )
        if self._write_char is None:
            raise RuntimeError(
                f"Write characteristic (handle 0x{WRITE_HANDLE:04x}) not found"
            )

        await self._client.start_notify(self._notify_char, self._on_notification)
        return self

    async def __aexit__(self, *_) -> None:
        try:
            if self._notify_char is not None:
                await self._client.stop_notify(self._notify_char)
        except Exception:
            pass
        await self._client.disconnect()

    # ---- internals --------------------------------------------------------

    def _on_notification(self, _handle: int, data: bytearray) -> None:
        payload = bytes(data)

        # Resolve any waiting futures keyed on payload prefix
        prefix = payload[:3] if len(payload) >= 3 else payload
        for key in list(self._pending.keys()):
            if payload[:len(key)] == key:
                fut = self._pending.pop(key)
                if not fut.done():
                    fut.set_result(payload)
                break

        if self._notification_callback:
            self._notification_callback(payload)

    async def _write(self, data: bytes) -> None:
        await self._client.write_gatt_char(
            self._write_char, data, response=False
        )

    async def _write_and_wait(
        self,
        data: bytes,
        response_prefix: bytes,
        timeout: float = 5.0,
    ) -> bytes:
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[bytes] = loop.create_future()
        self._pending[response_prefix] = fut
        await self._write(data)
        return await asyncio.wait_for(fut, timeout=timeout)

    # ---- public API -------------------------------------------------------

    @property
    def address(self) -> str:
        return self._device.address

    @property
    def name(self) -> str:
        return self._device.name or self._device.address

    async def startup(self, volume: int = VOLUME_MAX) -> StartupSnapshot:
        """
        Perform the confirmed startup exchange:
          1. Send startup query (0x35)
          2. Wait for startup snapshot (0x35 ... 13 bytes)
          3. Send initial volume (0x5b XX)

        Returns the decoded StartupSnapshot.
        """
        response = await self._write_and_wait(
            build_startup_query(),
            response_prefix=bytes([MSG_STARTUP_SNAPSHOT]),
            timeout=5.0,
        )
        snapshot = decode_startup_snapshot(response)
        if snapshot is None:
            raise RuntimeError(
                f"Unexpected startup response: {response.hex()}"
            )
        await self._write(build_volume_set(volume))
        return snapshot

    async def write_config(
        self, level: int, name_a: int, name_b: int
    ) -> None:
        """
        Write level and name configuration to the gun (form A config write + apply).

        ``name_a`` and ``name_b`` are the raw byte values to embed in the
        config-write payload (bytes 9 and 10).  Based on capture evidence,
        these appear to equal (app_name_index + 1) for each selected name
        word, but this relationship is inferred.
        """
        await self._write(build_config_write(level, name_a, name_b))
        await self._write(build_apply_commit())

    async def set_volume(self, volume: int) -> None:
        """Set gun volume (0 = mute, 31 = max).  Confirmed by Test 4."""
        await self._write(build_volume_set(volume))

    async def poll_status(self) -> bytes:
        """Send a status poll and return the raw 3-byte status reply."""
        return await self._write_and_wait(
            build_status_poll(),
            response_prefix=bytes([MSG_STATUS_REPLY, ]),
            timeout=5.0,
        )

    async def collect_stats(
        self,
        stat_types: tuple[int, ...] = (0x01, 0x02, 0x06),
        per_type_timeout: float = 5.0,
    ) -> list[list[StatCounterReply]]:
        """
        Request end-of-game statistics for each stat type and collect replies.

        Sends ``5a3f01 TT 0000`` for each TT in ``stat_types``, then
        collects ``30013f TT NN`` replies until the terminal marker (3e0100)
        is seen or a timeout elapses.

        Returns a list of lists (one per stat_type) of StatCounterReply objects.
        """
        results: list[list[StatCounterReply]] = []
        terminal = bytes([0x3E, 0x01, 0x00])

        for stat_type in stat_types:
            replies: list[StatCounterReply] = []
            done = asyncio.Event()

            original_cb = self._notification_callback

            def _cb(payload: bytes) -> None:
                sc = decode_stat_counter(payload)
                if sc is not None and sc.stat_type == stat_type:
                    replies.append(sc)
                if payload == terminal:
                    done.set()
                if original_cb:
                    original_cb(payload)

            self._notification_callback = _cb
            try:
                await self._write(build_stat_request(stat_type))
                try:
                    await asyncio.wait_for(done.wait(), timeout=per_type_timeout)
                except asyncio.TimeoutError:
                    pass
            finally:
                self._notification_callback = original_cb

            results.append(replies)

        return results

    async def close_session(self) -> None:
        """Send the session-close command (0x42, low-medium confidence)."""
        await self._write(build_session_close())


# ---------------------------------------------------------------------------
# Discovery helper
# ---------------------------------------------------------------------------

async def scan_for_devices(
    timeout: float = 10.0,
    name_filter: str = DEVICE_NAME,
    use_service_uuid: bool = True,
) -> list[BLEDevice]:
    """
    Return nearby LaserOps blasters.

    By default scans for the advertised service UUID (most reliable). Falls
    back to a case-insensitive device-name substring match when
    ``use_service_uuid`` is False.

    All LaserOps blasters advertise:
      - Device Name (AD type 0x09): "NerfV"
      - 128-bit Service UUID (AD type 0x07): 073e1435-85d1-455c-97cd-0b8262f20eac
    """
    if use_service_uuid:
        devices = await BleakScanner.discover(
            timeout=timeout,
            service_uuids=[SERVICE_UUID],
        )
        return list(devices)
    else:
        devices = await BleakScanner.discover(timeout=timeout)
        needle = name_filter.lower()
        return [
            d for d in devices
            if d.name and needle in d.name.lower()
        ]

