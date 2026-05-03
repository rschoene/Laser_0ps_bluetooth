#!/usr/bin/env python3
"""
assign_device.py — Set player name, ID, and team on a LaserOps blaster.

Usage:
    python assign_device.py --address E4:FE:7C:AA:11:22 \
                            --name "Player1" \
                            --player-id 1 \
                            --team 0
"""

import argparse
import asyncio

from bleak import BleakScanner

from laserops import LaserOpsDevice, GAME_MODE_NAMES


TEAM_NAMES = {0: "free-for-all", 1: "red", 2: "blue"}


async def main(address: str, name: str, player_id: int, team_id: int) -> None:
    # If no address given, scan and let the user pick
    if not address:
        print("No address specified — scanning for 10 s …")
        devices = await BleakScanner.discover(timeout=10.0)
        candidates = [d for d in devices if d.name and "LaserOps" in d.name]
        if not candidates:
            print("No LaserOps devices found.")
            return
        for i, d in enumerate(candidates, 1):
            print(f"  [{i}] {d.name}  {d.address}")
        idx = int(input("Select device number: ")) - 1
        device = candidates[idx]
    else:
        device = await BleakScanner.find_device_by_address(address, timeout=10.0)
        if device is None:
            print(f"Device {address} not found.")
            return

    print(f"Connecting to {device.name} ({device.address}) …")
    async with LaserOpsDevice(device) as gun:
        info = await gun.handshake()
        print(
            f"  Firmware: {info.firmware_version}  "
            f"Battery: {info.battery_pct}%"
        )

        await gun.set_player(player_id=player_id, team_id=team_id, name=name)

        # Read back to confirm
        cfg = await gun.get_player()
        team_name = TEAM_NAMES.get(cfg.team_id, str(cfg.team_id))
        print(
            f"  ✓  Player set — id={cfg.player_id}, "
            f"team={team_name!r}, name={cfg.name!r}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Assign player name / ID / team to a LaserOps blaster."
    )
    parser.add_argument(
        "--address", default="",
        help="BLE address of the blaster (e.g. E4:FE:7C:AA:11:22). "
             "If omitted, a scan is performed.",
    )
    parser.add_argument("--name", default="Player", help="Player name (max 12 chars)")
    parser.add_argument("--player-id", type=int, default=1,
                        help="Player ID 1–8 (default: 1)")
    parser.add_argument("--team", type=int, default=0,
                        help="Team ID: 0=FFA, 1=red, 2=blue (default: 0)")
    args = parser.parse_args()
    asyncio.run(main(args.address, args.name, args.player_id, args.team))
