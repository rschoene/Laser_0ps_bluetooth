#!/usr/bin/env python3
"""
show_connected_guns.py — Discover LaserOps blasters and print current gun info.

Uses the incremental discovery stream and BlasterState sync routines from
laserops.py.

Examples:
    python scripts/show_connected_guns.py --count 1
    python scripts/show_connected_guns.py --count 4 --timeout 30
    python scripts/show_connected_guns.py --count 0 --timeout 0
"""

from __future__ import annotations

import argparse
import asyncio

from laserops import BlasterState, LaserOpsDevice, stream_discovered_devices


async def inspect_device(index: int, device) -> None:
    """Connect to one discovered device and print synchronized state."""
    rssi = getattr(device, "rssi", None)
    rssi_text = f"{rssi} dBm" if rssi is not None else "unknown"
    name = device.name or "unknown"

    print(f"[{index}] Found {name} ({device.address}) RSSI={rssi_text}")

    try:
        async with LaserOpsDevice(device) as gun:
            state = BlasterState(gun)
            snapshot = await state.sync_up(timeout=5.0)
            print(
                f"[{index}] Gun info: level={state.config.level} "
                f"name_a=0x{state.config.name_a:02x} "
                f"name_b=0x{state.config.name_b:02x} "
                f"raw={snapshot.raw.hex()}"
            )
    except Exception as exc:
        print(f"[{index}] Failed to inspect {device.address}: {exc}")


async def main(
    count: int,
    timeout: float,
    by_name: bool,
    name: str,
    lost_after: float,
) -> None:
    use_service_uuid = not by_name
    timeout_value = timeout if timeout > 0 else None

    if count < 0:
        raise ValueError("--count must be >= 0")

    if use_service_uuid:
        method = "service UUID"
    else:
        method = f"name contains '{name}'"

    timeout_text = f"{timeout:.1f}s" if timeout > 0 else "infinite"
    target_text = str(count) if count > 0 else "unbounded"
    print(f"Waiting for devices (target={target_text}, timeout={timeout_text}, filter={method}) ...")

    shown = 0
    async for device in stream_discovered_devices(
        timeout=timeout_value,
        name_filter=name,
        use_service_uuid=use_service_uuid,
        rediscover_on_reappear=True,
        lost_after=lost_after,
    ):
        shown += 1
        await inspect_device(shown, device)

        if count > 0 and shown >= count:
            break

    if shown == 0:
        print("No matching devices discovered.")
    else:
        print(f"Done. Displayed {shown} device(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Stream discovered LaserOps guns and display synced startup info "
            "(level + name bytes)."
        )
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of devices to inspect before stopping (0 = no fixed limit, default: 1)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=0.0,
        help="Discovery timeout in seconds (0 = infinite, default: 0)",
    )
    parser.add_argument(
        "--by-name",
        action="store_true",
        help="Filter by device name instead of service UUID",
    )
    parser.add_argument(
        "--name",
        default="NerfV",
        help='Device name substring when using --by-name (default: "NerfV")',
    )
    parser.add_argument(
        "--lost-after",
        type=float,
        default=8.0,
        help=(
            "Seconds without advertisements before a gun is treated as lost "
            "and can be shown again after restart (default: 8.0)"
        ),
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(args.count, args.timeout, args.by_name, args.name, args.lost_after))
    except KeyboardInterrupt:
        print("\nStopped.")
