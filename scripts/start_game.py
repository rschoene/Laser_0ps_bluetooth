#!/usr/bin/env python3
"""
start_game.py — Configure and start a LaserOps game session.

All specified blasters are configured with matching game parameters and then
started simultaneously.

Usage:
    # Free-for-all, 10 minutes, unlimited lives
    python start_game.py --addresses E4:FE:7C:AA:11:22 E4:FE:7C:BB:33:44

    # Team deathmatch, 5 minutes, 3 lives, 5 s respawn
    python start_game.py --addresses E4:FE:7C:AA:11:22 E4:FE:7C:BB:33:44 \\
                         --mode team_deathmatch --duration 300 --lives 3 \\
                         --respawn 5

    # Stop a running game
    python start_game.py --addresses E4:FE:7C:AA:11:22 --stop
"""

import argparse
import asyncio
from typing import Sequence

from bleak import BleakScanner

from laserops import LaserOpsDevice, GAME_MODE_NAMES


async def main(
    addresses: Sequence[str],
    mode: int,
    duration_s: int,
    lives: int,
    respawn_s: int,
    friendly_fire: bool,
    stop: bool,
) -> None:
    if not addresses:
        print("No addresses specified. Use --addresses <addr1> [addr2 …]")
        return

    print(f"Connecting to {len(addresses)} device(s) …")
    guns: list[LaserOpsDevice] = []
    for addr in addresses:
        ble_dev = await BleakScanner.find_device_by_address(addr, timeout=10.0)
        if ble_dev is None:
            print(f"  ✗  {addr} not found — skipping.")
            continue
        gun = LaserOpsDevice(ble_dev)
        await gun.__aenter__()
        guns.append(gun)
        print(f"  ✓  Connected to {ble_dev.name} ({addr})")

    if not guns:
        print("No devices connected — aborting.")
        return

    try:
        if stop:
            print("Stopping game on all connected devices …")
            await asyncio.gather(*(g.stop_game() for g in guns))
            print("Done.")
            return

        # Handshake each gun
        for gun in guns:
            info = await gun.handshake()
            print(
                f"  {gun.name}: firmware={info.firmware_version} "
                f"battery={info.battery_pct}%"
            )

        # Push game configuration
        mode_name = {v: k for k, v in GAME_MODE_NAMES.items()}.get(mode, str(mode))
        print(
            f"\nGame config: mode={mode_name}, duration={duration_s}s, "
            f"lives={lives or '∞'}, respawn={respawn_s}s, "
            f"friendly_fire={friendly_fire}"
        )
        await asyncio.gather(
            *(g.set_game(
                mode=mode,
                duration_s=duration_s,
                lives=lives,
                respawn_s=respawn_s,
                friendly_fire=friendly_fire,
            ) for g in guns)
        )

        # Start simultaneously
        print("\nStarting game …")
        await asyncio.gather(*(g.start_game() for g in guns))
        print("✓  Game started!")

    finally:
        for gun in guns:
            await gun.__aexit__(None, None, None)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start a LaserOps game session.")
    parser.add_argument(
        "--addresses", nargs="+", default=[],
        metavar="ADDR",
        help="BLE addresses of the blasters to include in the game.",
    )
    parser.add_argument(
        "--mode", default="ffa",
        choices=list(GAME_MODE_NAMES.keys()),
        help="Game mode (default: ffa)",
    )
    parser.add_argument(
        "--duration", type=int, default=0,
        help="Game duration in seconds; 0 = unlimited (default: 0)",
    )
    parser.add_argument(
        "--lives", type=int, default=0,
        help="Lives per player; 0 = unlimited (default: 0)",
    )
    parser.add_argument(
        "--respawn", type=int, default=5,
        help="Respawn delay in seconds (default: 5)",
    )
    parser.add_argument(
        "--friendly-fire", action="store_true",
        help="Enable friendly fire (default: disabled)",
    )
    parser.add_argument(
        "--stop", action="store_true",
        help="Stop the current game instead of starting one.",
    )
    args = parser.parse_args()
    asyncio.run(
        main(
            addresses=args.addresses,
            mode=GAME_MODE_NAMES[args.mode],
            duration_s=args.duration,
            lives=args.lives,
            respawn_s=args.respawn,
            friendly_fire=args.friendly_fire,
            stop=args.stop,
        )
    )
