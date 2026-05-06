#!/usr/bin/env python3
"""
reaction_game.py — NERF LaserOps reaction trainer.

Connects to a LaserOps blaster, starts a single-player game session, then
prompts the player to SHOOT n times and then RELOAD in time.
Failing to perform the correct action within the time window deals 1 damage.
The game ends when HP reaches 0.

  SHOOT  = pull the physical trigger   → gun sends 0x49
  RELOAD = physically reload the gun   → gun sends 0x52

Usage:
    python reaction_game.py                        # scan and pick a device
    python reaction_game.py --address AA:BB:CC:DD  # connect directly
    python reaction_game.py --timeout 2.0          # 2-second reaction window
    python reaction_game.py --volume 50            # set volume to 50
"""
from __future__ import annotations

import argparse
import asyncio
import random
import sys
import time
from pathlib import Path
from typing import Optional

# Allow running directly from this subdirectory; scripts/ is one level up.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bleak import BleakScanner
from bleak.backends.device import BLEDevice

from laserops import (
    LaserOpsDevice,
    scan_for_devices,
    VOLUME_MIN,
    VOLUME_MAX,
)

# -----------------------------------------------------------------------
# Game-start sequence reproduced from start_game.py (first observed in
# Test 2; present in all subsequent single-player AR captures).
# Semantics are inferred from context — confidence: medium.
# -----------------------------------------------------------------------
_GAME_SETUP_COMMANDS: list[bytes] = [
    bytes.fromhex("4401"),
    bytes.fromhex("490100"),
    bytes.fromhex("4a0000000000000000001388"),
    bytes.fromhex("411388"),
    bytes.fromhex("3b07"),
    bytes.fromhex("390a"),
]

# Default assumed starting HP.  Updated from the first 30013f response.
_DEFAULT_HP = 10
_INITIAL_ROUND_TIMEOUT = 30.0
_INITIAL_WAIT_TIMEOUT = 30.0
_ROUND_TIMEOUT_STEP = 1.0
_MIN_ROUND_TIMEOUT = 5.0


# -----------------------------------------------------------------------
# Reaction game logic
# -----------------------------------------------------------------------

class ReactionGame:
    """Drives the round-based reaction loop on a connected gun."""

    def __init__(self, gun: LaserOpsDevice, reaction_timeout: float) -> None:
        self._gun = gun
        self._round_timeout = reaction_timeout
        self._action_queue: asyncio.Queue[str] = asyncio.Queue()
        self._hp_event = asyncio.Event()
        self._remaining_hp: Optional[int] = None
        self._active = False
        self._last_reload_event_ts = 0.0

    # ---- notification handler ----------------------------------------

    def _on_notification(self, payload: bytes) -> None:
        if not self._active:
            return

        def push_reload_once() -> None:
            now = time.monotonic()
            # Captures show reload as 0x52 followed by 0x310a/0x310d ~0.5 s later.
            # Treat them as one user action to avoid polluting the next round.
            if now - self._last_reload_event_ts >= 0.8:
                self._action_queue.put_nowait("reload")
                self._last_reload_event_ts = now

        if payload == bytes([0x49]):
            # Trigger pulled → shoot event
            self._action_queue.put_nowait("shoot")
        elif payload[:1] == bytes([0x52]) and len(payload) == 1:
            # Reload marker A → reload event
            push_reload_once()
        elif payload in (bytes.fromhex("310a"), bytes.fromhex("310d")):
            # Reload marker B (observed ~0.5 s after 0x52 in captures).
            push_reload_once()
        elif payload[:3] == bytes([0x30, 0x01, 0x3F]) and len(payload) == 5:
            # Damage-apply response: byte 4 = remaining HP
            self._remaining_hp = payload[4]
            self._hp_event.set()

    # ---- helpers -------------------------------------------------------

    async def _apply_damage(self, amount: int = 1) -> Optional[int]:
        """Send a damage request; return remaining HP or None on timeout."""
        self._hp_event.clear()
        await self._gun._write(  # noqa: SLF001
            bytes([0x5A, 0x3F, 0x01, amount & 0xFF, 0x00, 0x00])
        )
        try:
            await asyncio.wait_for(self._hp_event.wait(), timeout=3.0)
            return self._remaining_hp
        except asyncio.TimeoutError:
            return None

    def _drain_queue(self) -> None:
        """Discard stale events that arrived before the current prompt."""
        while not self._action_queue.empty():
            self._action_queue.get_nowait()

    # ---- main game loop ------------------------------------------------

    async def run(self) -> None:
        self._gun._notification_callback = self._on_notification  # noqa: SLF001
        self._active = True
        hp = _DEFAULT_HP
        round_num = 0

        print()
        print("╔══════════════════════════════╗")
        print("║   REACTION GAME  —  STARTED  ║")
        print("╚══════════════════════════════╝")
        print(f"  Starting HP : {hp} (updated on first hit)")
        print(f"  Round timer : {self._round_timeout:.1f} s")
        print("  Round task  : SHOOT N times (N=1..8), then RELOAD")
        print("  Correct round -> timer gets shorter")
        print("  Failed round  -> lose 1 HP")
        print()

        while True:
            round_num += 1
            required_shots = random.randint(1, 8)
            shots_left = required_shots

            self._drain_queue()

            print(
                f"[{round_num:4d}]  >>>  SHOOT x{required_shots}, then RELOAD  <<<"
            )

            success = False
            fail_reason = "too slow"
            deadline = asyncio.get_event_loop().time() + self._round_timeout

            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break

                try:
                    received = await asyncio.wait_for(
                        self._action_queue.get(),
                        timeout=remaining,
                    )
                except asyncio.TimeoutError:
                    break

                if shots_left > 0:
                    if received == "shoot":
                        shots_left -= 1
                        print(
                            f"          shot ok ({required_shots - shots_left}/{required_shots})"
                        )
                    elif received == "reload":
                        fail_reason = "reloaded too early"
                        break
                else:
                    if received == "reload":
                        success = True
                        break
                    elif received == "shoot":
                        fail_reason = "shot after sequence complete"
                        break

            if success:
                self._round_timeout = max(
                    _MIN_ROUND_TIMEOUT,
                    self._round_timeout - _ROUND_TIMEOUT_STEP,
                )
                print(
                    f"          ✓  next timer: {self._round_timeout:.1f} s"
                )
            else:
                print(f"          ✗  ({fail_reason})  -1 HP", end="  ", flush=True)

                confirmed_hp = await self._apply_damage(1)
                if confirmed_hp is not None:
                    hp = confirmed_hp
                    print(f"HP: {hp}")
                else:
                    hp = max(0, hp - 1)
                    print(f"HP: {hp}  (no gun response)")

                if hp == 0:
                    print()
                    print("╔══════════════════╗")
                    print("║   ★  GAME OVER  ★ ║")
                    print("╚══════════════════╝")
                    print(f"  Survived {round_num} round(s).")
                    break
            # correct action: proceed immediately to next round

        self._active = False


# -----------------------------------------------------------------------
# Device selection
# -----------------------------------------------------------------------

async def pick_device(address: Optional[str], timeout: Optional[float]) -> Optional[BLEDevice]:
    """Return the BLE device to connect to, scanning if no address given."""
    if timeout is None:
        timeout = 15.0
    if address:
        print(f"Looking for {address} …")
        return await BleakScanner.find_device_by_address(address, timeout=timeout)
    print(f"Scanning for LaserOps devices ({timeout:.0f} s) …")
    devices = await scan_for_devices(timeout=timeout)
    if not devices:
        print("No devices found.")
        return None
    if len(devices) == 1:
        print(f"  Found: {devices[0].name}  ({devices[0].address})")
        return devices[0]

    for i, d in enumerate(devices, 1):
        rssi = getattr(d, "rssi", None)
        rssi_str = f"{rssi} dBm" if rssi is not None else "?"
        print(f"  [{i}]  {(d.name or 'unknown'):<30}  {d.address}  {rssi_str}")

    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(
        None, lambda: input(f"Select device [1-{len(devices)}]: ").strip()
    )
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(devices):
            return devices[idx]
    except ValueError:
        pass
    print("Invalid selection.")
    return None


# -----------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------

async def main(address: Optional[str], volume: int, reaction_timeout: float, timeout: Optional[float]) -> None:
    dev = await pick_device(address, timeout)
    if dev is None:
        sys.exit(1)

    print(f"Connecting to {dev.name or dev.address} …")
    async with LaserOpsDevice(dev) as gun:
        print("  Startup exchange …")
        snapshot = await gun.startup(volume=volume)
        print(
            f"  Gun: level={snapshot.level} "
            f"name_bytes=(0x{snapshot.name_a:02x}, 0x{snapshot.name_b:02x})"
        )

        print("  Sending game-start sequence …")
        for cmd in _GAME_SETUP_COMMANDS:
            await gun._write(cmd)  # noqa: SLF001
            await asyncio.sleep(0.05)
        print("  Game armed.")

        game = ReactionGame(gun, reaction_timeout=reaction_timeout)
        await game.run()

        print("  Closing session …")
        await gun.close_session()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "NERF LaserOps reaction trainer — perform the correct action within "
            "the time window or take 1 damage."
        )
    )
    parser.add_argument(
        "--address", default=None,
        help="BLE address of the blaster (omit to scan and pick)",
    )
    parser.add_argument(
        "--volume", type=int, default=VOLUME_MIN,
        help=f"Gun startup volume 0–31 (default: 0x{VOLUME_MIN:02x})",
    )
    parser.add_argument(
        "--reacttimeout", type=float, default=_INITIAL_ROUND_TIMEOUT,
        help=(
            "Initial round timer in seconds for 'shoot N then reload' "
            f"(default: {_INITIAL_ROUND_TIMEOUT:.0f})"
        ),
    )
    parser.add_argument(
        "--timeout", type=float, default=_INITIAL_WAIT_TIMEOUT,
        help=(
            "Initial wait timer in seconds "
            f"(default: {_INITIAL_WAIT_TIMEOUT:.0f})"
        ),
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(args.address, args.volume, args.reacttimeout, args.timeout))
    except KeyboardInterrupt:
        print("\nAborted.")
