#!/usr/bin/env python3
"""
hand_out_level_on_connect.py - Auto-assign a level to discovered LaserOps devices.

This script scans for nearby LaserOps blasters and, for each newly discovered
device, connects and writes a target level while preserving the current name
bytes from the startup snapshot.

Usage examples:
    python hand_out_level_on_connect.py --level 5 --once
    python hand_out_level_on_connect.py --level 3 --continuous
    python hand_out_level_on_connect.py --level 4 --timeout 60 --by-name
"""

from __future__ import annotations

import argparse
import asyncio

from laserops import LaserOpsDevice, stream_discovered_devices


async def assign_level_to_device(
    device,
    level: int,
    verify: bool,
    startup_timeout: float,
) -> bool:
    """Connect to one device and write the requested level."""
    print(f"Connecting to {(device.name or 'unknown')} ({device.address}) ...")

    try:
        async with LaserOpsDevice(device) as gun:
            before = await gun.query_startup_snapshot(timeout=startup_timeout)
            print(
                f"  Current: level={before.level}, "
                f"name_parts=(0x{before.name_a:02x}, 0x{before.name_b:02x})"
            )

            if before.level == level:
                print("  Level already matches target. Skipping write.")
                return True

            await gun.write_config(level=level, name_a=before.name_a, name_b=before.name_b)
            print(f"  Wrote level={level} and sent apply/commit.")

            if verify:
                after = await gun.query_startup_snapshot(timeout=startup_timeout)
                print(
                    f"  Verify: level={after.level}, "
                    f"name_parts=(0x{after.name_a:02x}, 0x{after.name_b:02x})"
                )
                if after.level != level:
                    print("  WARNING: level verification did not match target.")
                    return False

            return True
    except Exception as exc:  # noqa: BLE001
        print(f"  Failed to assign level on {device.address}: {exc}")
        return False


async def main(
    level: int,
    timeout: float,
    once: bool,
    by_name: bool,
    name: str,
    verify: bool,
    rediscover: bool,
    lost_after: float,
    startup_timeout: float,
) -> None:
    mode = "name filter" if by_name else "service UUID"
    timeout_str = "infinite" if timeout <= 0 else f"{timeout:.0f}s"
    run_mode = "single-device" if once else "continuous"

    print(
        f"Watching for LaserOps devices ({run_mode}, timeout={timeout_str}, "
        f"filter={mode}) ..."
    )
    print(f"Target level: {level}")

    attempts = 0
    successes = 0
    seen_addresses: set[str] = set()

    stream_timeout = None if timeout <= 0 else timeout
    async for device in stream_discovered_devices(
        timeout=stream_timeout,
        name_filter=name,
        use_service_uuid=not by_name,
        rediscover_on_reappear=rediscover,
        lost_after=lost_after,
    ):
        addr = device.address.lower()

        # In non-rediscovery mode, avoid repeated connections from duplicate scan events.
        if not rediscover and addr in seen_addresses:
            continue
        seen_addresses.add(addr)

        attempts += 1
        ok = await assign_level_to_device(
            device=device,
            level=level,
            verify=verify,
            startup_timeout=startup_timeout,
        )
        if ok:
            successes += 1
            if once:
                break

    print(f"Done. attempts={attempts}, successes={successes}")
    if attempts == 0:
        print("No matching devices were discovered in the scan window.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Auto-assign a level to newly discovered LaserOps devices.",
    )
    parser.add_argument(
        "--level",
        type=int,
        required=True,
        help="Target level byte to write (for example: 5).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=0.0,
        help="Scan timeout in seconds (<=0 means run until interrupted).",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Stop after first successful assignment.",
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Continue handing out levels to newly discovered devices.",
    )
    parser.add_argument(
        "--by-name",
        action="store_true",
        help="Filter by device-name substring instead of service UUID.",
    )
    parser.add_argument(
        "--name",
        default="NerfV",
        help='Name substring used with --by-name (default: "NerfV").',
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip read-back verification after writing level.",
    )
    parser.add_argument(
        "--rediscover",
        action="store_true",
        help="Allow handling a device again after it disappears and reappears.",
    )
    parser.add_argument(
        "--lost-after",
        type=float,
        default=8.0,
        help="Seconds without advertisements before a device is considered gone.",
    )
    parser.add_argument(
        "--startup-timeout",
        type=float,
        default=5.0,
        help="Timeout for each startup snapshot query in seconds.",
    )

    args = parser.parse_args()

    once = True
    if args.continuous:
        once = False
    elif args.once:
        once = True

    asyncio.run(
        main(
            level=args.level,
            timeout=args.timeout,
            once=once,
            by_name=args.by_name,
            name=args.name,
            verify=not args.no_verify,
            rediscover=args.rediscover,
            lost_after=args.lost_after,
            startup_timeout=args.startup_timeout,
        )
    )