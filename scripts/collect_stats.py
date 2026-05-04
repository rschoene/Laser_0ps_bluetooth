#!/usr/bin/env python3
"""
collect_stats.py — Retrieve end-of-game statistics from a LaserOps blaster.

Protocol details (from Tests 2, 3, 6, 7 captures):
  - Host sends 6-byte stat request: 5a 3f 01 TT 00 00 (TT = 01, 02, or 06 observed)
  - Gun replies with 5-byte stat counters: 30 01 3f TT NN (NN descends to 00)
  - Gun sends terminal marker 3e 01 00 when done

The meaning of each stat type (TT) and counter value (NN) is inferred.
The upper bound of NN grows with gun level/upgrades (level 3: ~9, level 4: ~14).

Results are printed as raw observed values.  If --output is given, raw
per-type counter lists are saved as JSON for further analysis.

Usage:
    python collect_stats.py --address BLASTER_ADDR
    python collect_stats.py --address BLASTER_ADDR --output results.json
"""

import argparse
import asyncio
import json

from bleak import BleakScanner

from laserops import LaserOpsDevice, VOLUME_MAX, decode_notification


KNOWN_STAT_TYPES = (0x01, 0x02, 0x06)


async def main(address: str, output: str | None, volume: int) -> None:
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
        print(f"  Gun level: {snapshot.level}")

        print("  Requesting end-of-game statistics …")
        results_by_type = await gun.collect_stats(
            stat_types=KNOWN_STAT_TYPES,
            per_type_timeout=5.0,
        )

        print("\n--- Stat results ---")
        json_output = []
        for stat_type, replies in zip(KNOWN_STAT_TYPES, results_by_type):
            counters = [r.counter for r in replies]
            print(
                f"  type=0x{stat_type:02x}  "
                f"counters (descending): {[hex(c) for c in counters]}"
            )
            json_output.append({
                "stat_type": f"0x{stat_type:02x}",
                "counters": counters,
            })

        print(
            "\nNote: stat type semantics are inferred.  "
            "Counter values are raw bytes from the gun."
        )

        await gun.close_session()

    if output:
        with open(output, "w", encoding="utf-8") as fh:
            json.dump(
                {"address": address, "level": snapshot.level, "stats": json_output},
                fh,
                indent=2,
            )
        print(f"Raw results saved to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Collect end-of-game statistics from a LaserOps blaster."
    )
    parser.add_argument(
        "--address", required=True,
        help="BLE address of the blaster",
    )
    parser.add_argument(
        "--output", default=None, metavar="FILE",
        help="Save raw results as JSON to this file",
    )
    parser.add_argument(
        "--volume", type=int, default=0,
        help="Initial volume 0–31 (default: 0 = muted, avoids noise during collection)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.address, args.output, args.volume))

