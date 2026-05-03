#!/usr/bin/env python3
"""
collect_stats.py — Retrieve end-of-game statistics from LaserOps blasters.

Results are printed to stdout in a formatted table and optionally saved as JSON.

Usage:
    python collect_stats.py --addresses E4:FE:7C:AA:11:22 E4:FE:7C:BB:33:44

    # Save to JSON file
    python collect_stats.py --addresses E4:FE:7C:AA:11:22 E4:FE:7C:BB:33:44 \\
                            --output results.json
"""

import argparse
import asyncio
import json
from typing import Sequence

from bleak import BleakScanner

from laserops import LaserOpsDevice, GameStats


def _print_table(stats_list: list[tuple[str, GameStats]]) -> None:
    """Print statistics in a formatted table."""
    headers = [
        "Device", "PID", "Shots", "Hits\nScored", "Hits\nRecvd",
        "Kills", "Deaths", "Accuracy", "Duration",
    ]
    col_widths = [20, 4, 6, 8, 8, 6, 7, 9, 10]

    def fmt_row(values: Sequence[str]) -> str:
        return "  ".join(str(v).ljust(w) for v, w in zip(values, col_widths))

    header_line = fmt_row(
        ["Device", "PID", "Shots", "Scored", "Recvd",
         "Kills", "Deaths", "Accuracy", "Duration"]
    )
    print()
    print(header_line)
    print("-" * len(header_line))
    for device_name, s in stats_list:
        row = fmt_row([
            device_name[:20],
            str(s.player_id),
            str(s.shots_fired),
            str(s.hits_scored),
            str(s.hits_received),
            str(s.eliminations),
            str(s.deaths),
            f"{s.accuracy_pct}%",
            f"{s.game_duration_s}s",
        ])
        print(row)
    print()


async def collect_from_device(
    address: str,
) -> tuple[str, GameStats] | None:
    ble_dev = await BleakScanner.find_device_by_address(address, timeout=10.0)
    if ble_dev is None:
        print(f"  ✗  {address} not found — skipping.")
        return None

    async with LaserOpsDevice(ble_dev) as gun:
        await gun.handshake()
        stats = await gun.get_stats()
        return ble_dev.name or address, stats


async def main(addresses: Sequence[str], output: str | None) -> None:
    if not addresses:
        print("No addresses specified. Use --addresses <addr1> [addr2 …]")
        return

    print(f"Connecting to {len(addresses)} device(s) and collecting statistics …")

    tasks = [collect_from_device(addr) for addr in addresses]
    results_raw = await asyncio.gather(*tasks)

    results: list[tuple[str, GameStats]] = [r for r in results_raw if r is not None]

    if not results:
        print("No statistics retrieved.")
        return

    _print_table(results)

    if output:
        data = [
            {"device": name, "stats": s.to_dict()}
            for name, s in results
        ]
        with open(output, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        print(f"Results saved to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Collect end-of-game statistics from LaserOps blasters."
    )
    parser.add_argument(
        "--addresses", nargs="+", default=[],
        metavar="ADDR",
        help="BLE addresses of the blasters.",
    )
    parser.add_argument(
        "--output", default=None, metavar="FILE",
        help="Save results as JSON to this file.",
    )
    args = parser.parse_args()
    asyncio.run(main(args.addresses, args.output))
