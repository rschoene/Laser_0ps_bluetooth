#!/usr/bin/env python3
"""
assign_device.py — Write level and name configuration to a LaserOps blaster.

Protocol details (from Test 1 captures):
  - Startup sequence: host sends 0x35, gun replies with 13-byte 0x35 snapshot.
  - Config write: host sends 13-byte 0x36 payload with level byte and name-part bytes.
  - Apply/commit: host sends 0x57 after config write.

Name bytes (NN / MM in the payload) are inferred to be (app_name_index + 1)
based on Test 1 capture data.  The app uses separate scrollable word lists for
the first and second name word; the byte encodes the 1-based position within
the respective list (0-based index + 1).  This relationship is inferred, not
fully confirmed.

Name-space limits (IMPORTANT):
  The protocol byte is an 8-bit value (0x00–0xff), but the app's name-word
  lists are finite.  The highest name bytes ever observed across all test
  captures come from pre-existing gun names visible in startup snapshots:
    - First-name byte max: 0x32 = 50 (g3 startup "Zinc", Test 1)
    - Second-name byte max: 0x32 = 50 (g0 startup "Zombie", Test 1)
  Bytes above 0x32 have never been seen in any capture and are very likely
  to lie outside the valid name list; sending them may produce undefined
  behavior on the gun.  Do not exceed 0x32 unless you have verified the
  full name list size.

Usage:
    python assign_device.py --address BLASTER_ADDR \
                            --level 3 \\
                            --name-a 17 \\
                            --name-b 19
"""

import argparse
import asyncio

from bleak import BleakScanner

from laserops import LaserOpsDevice, VOLUME_MAX, decode_notification


async def main(
    address: str,
    level: int,
    name_a_index: int,
    name_b_index: int,
    volume: int,
) -> None:
    # Convert app UI name indices to protocol byte values (inferred: index + 1)
    name_a_byte = name_a_index + 1
    name_b_byte = name_b_index + 1

    ble_dev = await BleakScanner.find_device_by_address(address, timeout=15.0)
    if ble_dev is None:
        print(f"Device {address} not found.")
        return

    print(f"Connecting to {ble_dev.name} ({ble_dev.address}) …")

    def on_notification(payload: bytes) -> None:
        print(f"  [notify] {decode_notification(payload)}")

    async with LaserOpsDevice(ble_dev, notification_callback=on_notification) as gun:
        print("  Performing startup exchange (0x35 query / snapshot) …")
        snapshot = await gun.startup(volume=volume)
        print(
            f"  Gun reports: level={snapshot.level} "
            f"name_parts=(0x{snapshot.name_a:02x}, 0x{snapshot.name_b:02x})"
        )

        print(
            f"  Writing config: level={level}, "
            f"name_a_index={name_a_index} (byte=0x{name_a_byte:02x}), "
            f"name_b_index={name_b_index} (byte=0x{name_b_byte:02x}) …"
        )
        await gun.write_config(level=level, name_a=name_a_byte, name_b=name_b_byte)
        print("  ✓  Config written and apply/commit (0x57) sent.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Write level and name config to a LaserOps blaster.",
        epilog=(
            "Name indices correspond to the app's name-word list (0-based).  "
            "The protocol byte value is (index + 1) based on capture evidence "
            "(inferred, not fully confirmed)."
        ),
    )
    parser.add_argument(
        "--address", required=True,
        help="BLE address of the blaster (e.g. BLASTER_ADDR)",
    )
    parser.add_argument(
        "--level", type=int, required=True,
        help="Gun level to write (e.g. 3)",
    )
    parser.add_argument(
        "--name-a", type=int, default=0,
        metavar="INDEX",
        help=(
            "0-based index in the app's first-name word list (default: 0). "
            "Observed maximum across all test captures: index 49, byte 0x32 = 50 decimal "
            "('Zinc', g3 startup Test 1). "
            "Values above 49 are untested and may cause undefined behavior."
        ),
    )
    parser.add_argument(
        "--name-b", type=int, default=0,
        metavar="INDEX",
        help=(
            "0-based index in the app's second-name word list (default: 0). "
            "Observed maximum across all test captures: index 49, byte 0x32 = 50 decimal "
            "('Zombie', g0 startup Test 1). "
            "Values above 49 are untested and may cause undefined behavior."
        ),
    )
    parser.add_argument(
        "--volume", type=int, default=VOLUME_MAX,
        help=f"Initial volume byte 0–31 (default: {VOLUME_MAX} = max)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.address, args.level, args.name_a, args.name_b, args.volume))

