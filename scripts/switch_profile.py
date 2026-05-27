#!/usr/bin/env python3
"""

!! Untested – use at your own risk. No guarantee. !!

python scripts/switch_profile.py --address <MAC> --to alpha --dry-run
python scripts/switch_profile.py --address <MAC> --to alpha

switch_profile.py - Switch a blaster config template profile between alpha/delta.

This script writes a full 13-byte 0x36 config payload, then sends 0x57 commit.
It preserves current level/name bytes by default and verifies the resulting
startup snapshot after writing.

Known startup profile templates from captures:
  - alpha: 35 00 0a 02 02 01 00 0a LL NN MM 00 0a
  - delta: 35 00 12 01 02 00 01 0a LL NN MM 00 0a

Known matching config templates:
  - alpha: 36 00 0a 02 02 03 00 0a LL NN MM 00 04
  - delta: 36 00 12 01 02 00 01 0a LL NN MM 00 0a
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Literal

Profile = Literal["alpha", "delta", "unknown"]

_STARTUP_PREFIX_ALPHA = bytes.fromhex("35000a020201000a")
_STARTUP_PREFIX_DELTA = bytes.fromhex("350012010200010a")

_CONFIG_TEMPLATE_ALPHA = bytearray(bytes.fromhex("36000a020203000a0000000004"))
_CONFIG_TEMPLATE_DELTA = bytearray(bytes.fromhex("360012010200010a000000000a"))

_SAFE_LEVEL_MIN = 1
_SAFE_LEVEL_MAX = 5
_SAFE_NAME_MIN = 0x00
_SAFE_NAME_MAX = 0x32


def _detect_profile_from_snapshot(raw: bytes) -> Profile:
    if len(raw) == 13 and raw.startswith(_STARTUP_PREFIX_ALPHA):
        return "alpha"
    if len(raw) == 13 and raw.startswith(_STARTUP_PREFIX_DELTA):
        return "delta"
    return "unknown"


def _build_profile_config(
    *,
    target: Literal["alpha", "delta"],
    level: int,
    name_a: int,
    name_b: int,
) -> bytes:
    if target == "alpha":
        payload = bytearray(_CONFIG_TEMPLATE_ALPHA)
    else:
        payload = bytearray(_CONFIG_TEMPLATE_DELTA)
    payload[8] = level & 0xFF
    payload[9] = name_a & 0xFF
    payload[10] = name_b & 0xFF
    return bytes(payload)


def _ensure_range(name: str, value: int, lo: int, hi: int) -> int:
    if value < lo or value > hi:
        raise ValueError(f"{name} out of range ({value}, expected {lo}..{hi})")
    return int(value)


async def main(
    *,
    address: str,
    target_profile: Literal["alpha", "delta"],
    level: int | None,
    name_a: int | None,
    name_b: int | None,
    dry_run: bool,
) -> None:
    from bleak import BleakScanner

    from laserops import LaserOpsDevice, build_apply_commit, decode_notification

    ble_dev = await BleakScanner.find_device_by_address(address, timeout=15.0)
    if ble_dev is None:
        print(f"Device {address} not found.")
        return

    print(f"Connecting to {ble_dev.name or 'unknown'} ({ble_dev.address}) ...")

    def on_notification(payload: bytes) -> None:
        print(f"  [notify] {decode_notification(payload)}")

    async with LaserOpsDevice(ble_dev, notification_callback=on_notification) as gun:
        before = await gun.query_startup_snapshot(timeout=5.0)
        before_profile = _detect_profile_from_snapshot(before.raw)

        effective_level = before.level if level is None else level
        effective_name_a = before.name_a if name_a is None else name_a
        effective_name_b = before.name_b if name_b is None else name_b

        _ensure_range("level", effective_level, _SAFE_LEVEL_MIN, _SAFE_LEVEL_MAX)
        _ensure_range("name_a", effective_name_a, _SAFE_NAME_MIN, _SAFE_NAME_MAX)
        _ensure_range("name_b", effective_name_b, _SAFE_NAME_MIN, _SAFE_NAME_MAX)

        payload = _build_profile_config(
            target=target_profile,
            level=effective_level,
            name_a=effective_name_a,
            name_b=effective_name_b,
        )

        print(
            "Current snapshot: "
            f"profile={before_profile}, level={before.level}, "
            f"name_a=0x{before.name_a:02x}, name_b=0x{before.name_b:02x}, "
            f"raw={before.raw.hex()}"
        )
        print(
            "Planned write: "
            f"target_profile={target_profile}, "
            f"level={effective_level}, "
            f"name_a=0x{effective_name_a:02x}, "
            f"name_b=0x{effective_name_b:02x}, "
            f"payload={payload.hex()}"
        )

        if dry_run:
            print("Dry-run only, no write executed.")
            return

        # Intentional raw writes to send exact profile template bytes.
        await gun._write(payload)  # noqa: SLF001
        await gun._write(build_apply_commit())  # noqa: SLF001
        await asyncio.sleep(0.2)

        after = await gun.query_startup_snapshot(timeout=5.0)
        after_profile = _detect_profile_from_snapshot(after.raw)
        print(
            "After write: "
            f"profile={after_profile}, level={after.level}, "
            f"name_a=0x{after.name_a:02x}, name_b=0x{after.name_b:02x}, "
            f"raw={after.raw.hex()}"
        )

        if after_profile != target_profile:
            print(
                "WARNING: profile did not match requested target "
                f"({target_profile})."
            )
        else:
            print("OK: profile switch confirmed by startup snapshot.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Switch blaster profile template between alpha and delta "
            "using direct 0x36 writes."
        )
    )
    parser.add_argument("--address", required=True, help="BLE address")
    parser.add_argument(
        "--to",
        dest="target_profile",
        choices=("alpha", "delta"),
        required=True,
        help="Target profile template",
    )
    parser.add_argument(
        "--level",
        type=int,
        default=None,
        help="Level byte override (default: keep current snapshot level)",
    )
    parser.add_argument(
        "--name-a-byte",
        type=int,
        default=None,
        help="Name part A raw byte override (default: keep current)",
    )
    parser.add_argument(
        "--name-b-byte",
        type=int,
        default=None,
        help="Name part B raw byte override (default: keep current)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print current/target payload and exit without writing",
    )

    args = parser.parse_args()
    asyncio.run(
        main(
            address=args.address,
            target_profile=args.target_profile,
            level=args.level,
            name_a=args.name_a_byte,
            name_b=args.name_b_byte,
            dry_run=args.dry_run,
        )
    )
