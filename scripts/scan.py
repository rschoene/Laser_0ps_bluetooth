#!/usr/bin/env python3
"""
scan.py — Discover nearby NERF LaserOps blasters via BLE.

By default scans for the advertised service UUID
073e1435-85d1-455c-97cd-0b8262f20eac, which is the most reliable method.
All guns advertise the device name "NerfV"; use --by-name to filter by name
instead.

Usage:
    python scan.py [--timeout SECONDS] [--by-name] [--name TEXT]
"""

import argparse
import asyncio

from laserops import scan_for_devices


async def main(timeout: float, by_name: bool, name: str, expected_count: int) -> None:
    method = f"name contains '{name}'" if by_name else "service UUID"
    print(f"Scanning for LaserOps devices ({timeout:.0f} s, filter: {method}) …")
    devices = await scan_for_devices(
        timeout=timeout,
        name_filter=name,
        use_service_uuid=not by_name,
        expected_count=expected_count if expected_count > 0 else None,
    )

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
        "--by-name", action="store_true",
        help="Filter by device name substring instead of service UUID",
    )
    parser.add_argument(
        "--name", default="NerfV",
        help='Device name substring when using --by-name (default: "NerfV")',
    )
    parser.add_argument(
        "--expected-count", type=int, default=0,
        help=(
            "Stop scan early once this many matching devices are found "
            "(default: 0 = wait full timeout)"
        ),
    )
    args = parser.parse_args()
    asyncio.run(main(args.timeout, args.by_name, args.name, args.expected_count))

