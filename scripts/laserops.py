"""
laserops.py — Core BLE library for NERF LaserOps Pro blasters.

Provides:
  - Protocol constants (UUIDs, opcodes)
  - Packet builder / parser helpers
  - LaserOpsDevice: high-level async wrapper around a BLE connection
"""

from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass, field
from typing import Callable, Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

# ---------------------------------------------------------------------------
# Advertisement / device discovery
# ---------------------------------------------------------------------------

DEVICE_NAME_PREFIXES = ("LaserOps_Alpha", "LaserOps_Delta", "LaserOps")

# ---------------------------------------------------------------------------
# GATT UUIDs
# ---------------------------------------------------------------------------

SERVICE_DEVICE_INFO = "0000180a-0000-1000-8000-00805f9b34fb"

SERVICE_CONTROL = "0000aa00-0000-1000-8000-00805f9b34fb"
CHAR_COMMAND    = "0000aa01-0000-1000-8000-00805f9b34fb"  # Write
CHAR_STATUS     = "0000aa02-0000-1000-8000-00805f9b34fb"  # Notify
CHAR_PLAYER_CFG = "0000aa03-0000-1000-8000-00805f9b34fb"  # Read/Write
CHAR_GAME_CFG   = "0000aa04-0000-1000-8000-00805f9b34fb"  # Read/Write

SERVICE_STATS   = "0000bb00-0000-1000-8000-00805f9b34fb"
CHAR_STATS      = "0000bb01-0000-1000-8000-00805f9b34fb"  # Read/Notify
CHAR_HISTORY    = "0000bb02-0000-1000-8000-00805f9b34fb"  # Read

# ---------------------------------------------------------------------------
# Opcodes — commands (host → blaster)
# ---------------------------------------------------------------------------

CMD_HELLO      = 0x01
CMD_SET_PLAYER = 0x10
CMD_GET_PLAYER = 0x11
CMD_SET_GAME   = 0x20
CMD_START_GAME = 0x21
CMD_STOP_GAME  = 0x22
CMD_GET_STATS  = 0x30
CMD_RESET      = 0xF0

# Opcodes — events (blaster → host)
EVT_HELLO      = 0x81
EVT_PLAYER_CFG = 0x91
EVT_HIT        = 0xA0
EVT_SHOT_FIRED = 0xA1
EVT_ELIMINATED = 0xA2
EVT_RESPAWN    = 0xA3
EVT_GAME_END   = 0xB0
EVT_STATS      = 0xC0

PACKET_MAGIC = 0x4C  # 'L'

# ---------------------------------------------------------------------------
# Game mode constants
# ---------------------------------------------------------------------------

GAME_MODE_FFA              = 0
GAME_MODE_TEAM_DEATHMATCH  = 1
GAME_MODE_CAPTURE_THE_FLAG = 2
GAME_MODE_SURVIVAL         = 3

GAME_MODE_NAMES = {
    "ffa":               GAME_MODE_FFA,
    "team_deathmatch":   GAME_MODE_TEAM_DEATHMATCH,
    "capture_the_flag":  GAME_MODE_CAPTURE_THE_FLAG,
    "survival":          GAME_MODE_SURVIVAL,
}

# ---------------------------------------------------------------------------
# Packet helpers
# ---------------------------------------------------------------------------

def _checksum(data: bytes) -> int:
    """XOR checksum over all bytes."""
    result = 0
    for b in data:
        result ^= b
    return result


def build_packet(opcode: int, payload: bytes = b"") -> bytes:
    """Build a framed LaserOps command packet."""
    header = bytes([PACKET_MAGIC, opcode, len(payload)])
    cs = _checksum(header + payload)
    return header + payload + bytes([cs])


def parse_packet(data: bytes) -> tuple[int, bytes]:
    """
    Parse a raw notification into (opcode, payload).

    Raises ValueError if the packet is malformed or has a bad checksum.
    """
    if len(data) < 4:
        raise ValueError(f"Packet too short: {data.hex()}")
    if data[0] != PACKET_MAGIC:
        raise ValueError(f"Bad magic byte: 0x{data[0]:02X}")
    opcode = data[1]
    length = data[2]
    if len(data) != length + 4:
        raise ValueError(
            f"Length mismatch: header says {length} payload bytes "
            f"but got {len(data) - 4}"
        )
    payload = data[3 : 3 + length]
    expected_cs = _checksum(data[:-1])
    if data[-1] != expected_cs:
        raise ValueError(
            f"Checksum mismatch: got 0x{data[-1]:02X}, expected 0x{expected_cs:02X}"
        )
    return opcode, payload


# ---------------------------------------------------------------------------
# Data classes for parsed events
# ---------------------------------------------------------------------------

@dataclass
class HelloInfo:
    device_nonce: int
    firmware_version: str  # e.g. "1.2.0"
    battery_pct: int


@dataclass
class PlayerConfig:
    player_id: int
    team_id: int
    name: str


@dataclass
class HitEvent:
    shooter_id: int
    shooter_team: int
    damage: int
    health_left: int


@dataclass
class GameEndEvent:
    reason: int     # 0=time_up, 1=stopped, 2=winner
    winner_id: int
    winner_team: int


@dataclass
class GameStats:
    player_id: int
    shots_fired: int
    hits_received: int
    hits_scored: int
    eliminations: int
    deaths: int
    game_duration_s: int
    accuracy_pct: int

    def to_dict(self) -> dict:
        return {
            "player_id":      self.player_id,
            "shots_fired":    self.shots_fired,
            "hits_received":  self.hits_received,
            "hits_scored":    self.hits_scored,
            "eliminations":   self.eliminations,
            "deaths":         self.deaths,
            "game_duration_s":self.game_duration_s,
            "accuracy_pct":   self.accuracy_pct,
        }


# ---------------------------------------------------------------------------
# Event parsers
# ---------------------------------------------------------------------------

def parse_hello(payload: bytes) -> HelloInfo:
    if len(payload) < 7:
        raise ValueError("EVT_HELLO payload too short")
    device_nonce = struct.unpack_from("<I", payload, 0)[0]
    fw_bcd = struct.unpack_from("<H", payload, 4)[0]
    fw_str = f"{(fw_bcd >> 8) & 0xFF}.{(fw_bcd >> 4) & 0xF}.{fw_bcd & 0xF}"
    battery_pct = payload[6]
    return HelloInfo(device_nonce=device_nonce, firmware_version=fw_str,
                     battery_pct=battery_pct)


def parse_player_cfg(payload: bytes) -> PlayerConfig:
    if len(payload) < 3:
        raise ValueError("EVT_PLAYER_CFG payload too short")
    player_id = payload[0]
    team_id   = payload[1]
    name_len  = payload[2]
    name      = payload[3 : 3 + name_len].decode("utf-8", errors="replace")
    return PlayerConfig(player_id=player_id, team_id=team_id, name=name)


def parse_hit(payload: bytes) -> HitEvent:
    if len(payload) < 4:
        raise ValueError("EVT_HIT payload too short")
    return HitEvent(
        shooter_id=payload[0],
        shooter_team=payload[1],
        damage=payload[2],
        health_left=payload[3],
    )


def parse_game_end(payload: bytes) -> GameEndEvent:
    if len(payload) < 3:
        raise ValueError("EVT_GAME_END payload too short")
    return GameEndEvent(reason=payload[0], winner_id=payload[1],
                        winner_team=payload[2])


def parse_stats(payload: bytes) -> GameStats:
    if len(payload) < 14:
        raise ValueError("EVT_STATS payload too short")
    (player_id, shots_fired, hits_received, hits_scored,
     eliminations, deaths, game_duration_s, accuracy_pct) = struct.unpack_from(
        "<BHHHHHHB", payload, 0
    )
    return GameStats(
        player_id=player_id,
        shots_fired=shots_fired,
        hits_received=hits_received,
        hits_scored=hits_scored,
        eliminations=eliminations,
        deaths=deaths,
        game_duration_s=game_duration_s,
        accuracy_pct=accuracy_pct,
    )


# ---------------------------------------------------------------------------
# Command builders
# ---------------------------------------------------------------------------

def cmd_hello(host_nonce: int) -> bytes:
    payload = struct.pack("<I", host_nonce)
    return build_packet(CMD_HELLO, payload)


def cmd_set_player(player_id: int, team_id: int, name: str) -> bytes:
    name_bytes = name.encode("utf-8")[:12]
    payload = bytes([player_id, team_id, len(name_bytes)]) + name_bytes
    return build_packet(CMD_SET_PLAYER, payload)


def cmd_get_player() -> bytes:
    return build_packet(CMD_GET_PLAYER)


def cmd_set_game(
    mode: int,
    duration_s: int,
    lives: int,
    respawn_s: int,
    friendly_fire: bool,
) -> bytes:
    payload = struct.pack("<BHBBB", mode, duration_s, lives, respawn_s,
                          int(friendly_fire))
    return build_packet(CMD_SET_GAME, payload)


def cmd_start_game() -> bytes:
    return build_packet(CMD_START_GAME)


def cmd_stop_game() -> bytes:
    return build_packet(CMD_STOP_GAME)


def cmd_get_stats() -> bytes:
    return build_packet(CMD_GET_STATS)


def cmd_reset() -> bytes:
    return build_packet(CMD_RESET)


# ---------------------------------------------------------------------------
# High-level device class
# ---------------------------------------------------------------------------

EventCallback = Callable[[int, bytes], None]


class LaserOpsDevice:
    """
    Async context manager representing a connection to a single LaserOps blaster.

    Usage::

        async with LaserOpsDevice(ble_device) as gun:
            await gun.handshake()
            await gun.set_player(player_id=1, team_id=0, name="Player1")
            ...
    """

    def __init__(
        self,
        device: BLEDevice,
        event_callback: Optional[EventCallback] = None,
    ) -> None:
        self._device = device
        self._client = BleakClient(device)
        self._event_callback = event_callback
        self._pending: dict[int, asyncio.Future] = {}

    # ---- context manager --------------------------------------------------

    async def __aenter__(self) -> "LaserOpsDevice":
        await self._client.connect()
        await self._client.start_notify(CHAR_STATUS, self._on_notification)
        return self

    async def __aexit__(self, *_) -> None:
        try:
            await self._client.stop_notify(CHAR_STATUS)
        except Exception:
            pass
        await self._client.disconnect()

    # ---- internals --------------------------------------------------------

    def _on_notification(self, _handle: int, data: bytearray) -> None:
        try:
            opcode, payload = parse_packet(bytes(data))
        except ValueError:
            return
        # Resolve any waiting futures
        fut = self._pending.pop(opcode, None)
        if fut is not None and not fut.done():
            fut.set_result(payload)
        # Call user callback
        if self._event_callback:
            self._event_callback(opcode, payload)

    async def _send(self, packet: bytes) -> None:
        await self._client.write_gatt_char(CHAR_COMMAND, packet,
                                           response=True)

    async def _send_and_wait(
        self,
        packet: bytes,
        response_opcode: int,
        timeout: float = 5.0,
    ) -> bytes:
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[bytes] = loop.create_future()
        self._pending[response_opcode] = fut
        await self._send(packet)
        return await asyncio.wait_for(fut, timeout=timeout)

    # ---- public API -------------------------------------------------------

    @property
    def address(self) -> str:
        return self._device.address

    @property
    def name(self) -> str:
        return self._device.name or self._device.address

    async def handshake(self) -> HelloInfo:
        """Exchange nonces and retrieve firmware version / battery level."""
        import random
        nonce = random.getrandbits(32)
        payload = await self._send_and_wait(cmd_hello(nonce), EVT_HELLO)
        return parse_hello(payload)

    async def set_player(
        self, player_id: int, team_id: int = 0, name: str = ""
    ) -> None:
        """Set player identity on the blaster."""
        await self._send(cmd_set_player(player_id, team_id, name))

    async def get_player(self) -> PlayerConfig:
        """Retrieve current player configuration from the blaster."""
        payload = await self._send_and_wait(cmd_get_player(), EVT_PLAYER_CFG)
        return parse_player_cfg(payload)

    async def set_game(
        self,
        mode: int = GAME_MODE_FFA,
        duration_s: int = 0,
        lives: int = 0,
        respawn_s: int = 5,
        friendly_fire: bool = False,
    ) -> None:
        """Configure game parameters."""
        await self._send(
            cmd_set_game(mode, duration_s, lives, respawn_s, friendly_fire)
        )

    async def start_game(self) -> None:
        """Start the configured game."""
        await self._send(cmd_start_game())

    async def stop_game(self) -> None:
        """Stop the current game."""
        await self._send(cmd_stop_game())

    async def get_stats(self) -> GameStats:
        """Retrieve end-of-game statistics."""
        payload = await self._send_and_wait(cmd_get_stats(), EVT_STATS)
        return parse_stats(payload)

    async def reset(self) -> None:
        """Soft-reset the blaster."""
        await self._send(cmd_reset())


# ---------------------------------------------------------------------------
# Discovery helper
# ---------------------------------------------------------------------------

async def scan_for_devices(timeout: float = 10.0) -> list[BLEDevice]:
    """Return a list of LaserOps BLE devices visible nearby."""
    devices = await BleakScanner.discover(timeout=timeout)
    results = []
    for d in devices:
        if d.name and any(d.name.startswith(p) for p in DEVICE_NAME_PREFIXES):
            results.append(d)
    return results
