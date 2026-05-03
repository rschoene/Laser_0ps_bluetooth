#!/usr/bin/env python3
"""
scan.py — Discover nearby NERF LaserOps Pro blasters via BLE.

Usage:
    python scan.py [--timeout SECONDS]
"""

import argparse
import asyncio

from laserops import scan_for_devices


async def main(timeout: float) -> None:
    print(f"Scanning for LaserOps devices ({timeout:.0f} s) …")
    devices = await scan_for_devices(timeout=timeout)

    if not devices:
        print("No LaserOps devices found.")
        return

    for i, d in enumerate(devices, start=1):
        rssi = getattr(d, "rssi", None)
        rssi_str = f"RSSI {rssi} dBm" if rssi is not None else "RSSI unknown"
        print(f"  [{i}]  {d.name:<25}  {d.address}   {rssi_str}")

    print(f"Found {len(devices)} device(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scan for LaserOps BLE devices.")
    parser.add_argument(
        "--timeout", type=float, default=10.0,
        help="Scan duration in seconds (default: 10)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.timeout))
