#!/usr/bin/env python3
"""
start_game.py — Send the game-start command sequence to a LaserOps blaster.

The commands used here were first observed in Test 2 (single-player AR mode)
and are consistently present in all subsequent AR game session captures
(Tests 3–7), all of which use the same single-player AR mode.
Exact semantics are inferred from context; confidence is medium.

Observed sequence at start of every AR game session (host → gun, handle 0x0026):
  35            startup query
  5b 1f         initial volume
  36 ...        config write
  57            apply/commit
  44 01         game mode init flag (inferred)
  49 01 00      game option toggle (inferred)
  4a 00 00 00 00 00 00 00 00 00 13 88   timed game setup — 0x1388=5000 (inferred)
  41 13 88      setup parameter paired with 4a (inferred)
  3b 07         setup parameter (inferred)
  39 0a         setup parameter (inferred)

Usage:
    python start_game.py --address BLASTER_ADDR
    python start_game.py --address BLASTER_ADDR --level 3 --name-a 17 --name-b 19
"""

import argparse
import asyncio

from bleak import BleakScanner

from laserops import (
    LaserOpsDevice,
    VOLUME_MAX,
    build_config_write,
    build_apply_commit,
    decode_notification,
)

# Game-setup command bytes consistently observed at the start of every AR game
# session (first identified in Test 2; present in all subsequent Tests 3–7
# which all use the same single-player AR mode).  Exact semantics are inferred
# from context, not proven — confidence: medium.
_GAME_SETUP_COMMANDS = [
    bytes.fromhex("4401"),
    bytes.fromhex("490100"),
    bytes.fromhex("4a0000000000000000001388"),
    bytes.fromhex("411388"),
    bytes.fromhex("3b07"),
    bytes.fromhex("390a"),
]


async def main(
    address: str,
    level: int,
    name_a_byte: int,
    name_b_byte: int,
    volume: int,
    delay: float,
) -> None:
    ble_dev = await BleakScanner.find_device_by_address(address, timeout=15.0)
    if ble_dev is None:
        print(f"Device {address} not found.")
        return

    print(f"Connecting to {ble_dev.name} ({ble_dev.address}) …")

    def on_notification(payload: bytes) -> None:
        print(f"  [notify] {decode_notification(payload)}")

    async with LaserOpsDevice(ble_dev, notification_callback=on_notification) as gun:
        print("  Startup exchange …")
        snapshot = await gun.startup(volume=volume)
        print(
            f"  Gun snapshot: level={snapshot.level} "
            f"name_parts=(0x{snapshot.name_a:02x}, 0x{snapshot.name_b:02x})"
        )

        print("  Writing config …")
        await gun.write_config(level=level, name_a=name_a_byte, name_b=name_b_byte)

        print(
            "  Sending game-setup commands "
            "(observed in Test 2; semantics inferred) …"
        )
        for cmd in _GAME_SETUP_COMMANDS:
            print(f"    -> {cmd.hex()}")
            await gun._write(cmd)  # noqa: SLF001 — direct write intentional here
            if delay > 0:
                await asyncio.sleep(delay)

        print("  ✓  Game-start sequence sent.")
        print(
            "  Note: the meaning of the setup commands is not fully confirmed. "
            "Observe the gun's behavior and capture BLE traffic to verify."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Send the game-start command sequence to a LaserOps blaster. "
            "Commands are reproduced from Test 2 captures; semantics are inferred."
        )
    )
    parser.add_argument(
        "--address", required=True,
        help="BLE address of the blaster",
    )
    parser.add_argument(
        "--level", type=int, default=1,
        help="Level byte to write in config (default: 1)",
    )
    parser.add_argument(
        "--name-a", type=int, default=0, metavar="BYTE",
        help="Name-part A byte (raw, default: 0)",
    )
    parser.add_argument(
        "--name-b", type=int, default=0, metavar="BYTE",
        help="Name-part B byte (raw, default: 0)",
    )
    parser.add_argument(
        "--volume", type=int, default=VOLUME_MAX,
        help=f"Initial volume 0–31 (default: {VOLUME_MAX})",
    )
    parser.add_argument(
        "--delay", type=float, default=0.1,
        help="Delay in seconds between game-setup commands (default: 0.1)",
    )
    args = parser.parse_args()
    asyncio.run(
        main(
            address=args.address,
            level=args.level,
            name_a_byte=args.name_a,
            name_b_byte=args.name_b,
            volume=args.volume,
            delay=args.delay,
        )
    )

