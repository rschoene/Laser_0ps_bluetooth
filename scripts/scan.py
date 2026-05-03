#!/usr/bin/env python3
"""
scan.py — Discover nearby NERF LaserOps blasters via BLE.

Scans for devices whose advertisement name contains "laser" (the same
search criterion the official app uses).

Usage:
    python scan.py [--timeout SECONDS] [--name-contains TEXT]
"""

import argparse
import asyncio

from laserops import scan_for_devices


async def main(timeout: float, name_contains: str) -> None:
    print(f"Scanning for LaserOps devices ({timeout:.0f} s) …")
    devices = await scan_for_devices(timeout=timeout, name_contains=name_contains)

    if not devices:
        print("No matching devices found.")
        return

    for i, d in enumerate(devices, start=1):
        rssi = getattr(d, "rssi", None)
        rssi_str = f"RSSI {rssi} dBm" if rssi is not None else "RSSI unknown"
        print(f"  [{i}]  {(d.name or 'unknown'):<30}  {d.address}   {rssi_str}")

    print(f"Found {len(devices)} device(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scan for LaserOps BLE devices.")
    parser.add_argument(
        "--timeout", type=float, default=10.0,
        help="Scan duration in seconds (default: 10)",
    )
    parser.add_argument(
        "--name-contains", default="laser",
        help='Filter by device name substring (default: "laser")',
    )
    args = parser.parse_args()
    asyncio.run(main(args.timeout, args.name_contains))

