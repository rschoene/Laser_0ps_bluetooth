#!/usr/bin/env python3
"""Example BLE client for the LaserOps reverse-engineered protocol.

Features:
- waits for target device(s)
- optional pairing
- connects with debug prints
- resolves characteristics by ATT handle (0x0023 notify, 0x0026 write)
- starts notifications and decodes known payload families
- sends basic startup writes (35, 5bXX)

Dependencies:
  pip install bleak
"""

from __future__ import annotations

import argparse
import asyncio
import json
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List

from bleak import BleakClient, BleakScanner


@dataclass
class TargetDevice:
    name: str
    address: str


def hex_bytes(data: bytes) -> str:
    return data.hex()


def load_protocol(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_int_hex(v: str) -> int:
    return int(v, 16)


def decode_notification(payload: bytes) -> str:
    h = payload.hex()
    if h.startswith("35") and len(payload) == 13:
        level = payload[8]
        name_a = payload[9]
        name_b = payload[10]
        return f"startup_snapshot level={level} name_parts=({name_a:#04x},{name_b:#04x}) raw={h}"

    if h.startswith("51") and len(payload) == 3:
        status_word = (payload[1] << 8) | payload[2]
        return f"status_reply 0x{status_word:04x} raw={h}"

    if h == "49":
        return "trigger_event"

    if h == "52":
        return "reload_marker_a"

    if h in {"310a", "310d"}:
        return f"reload_marker_b mode={h[2:]}"

    if h.startswith("32") and len(payload) >= 3:
        family = h[:4]
        counter = payload[-1]
        return f"ammo_state family={family} counter=0x{counter:02x} raw={h}"

    if h.startswith("30013f") and len(payload) == 6:
        stat_type = payload[4]
        counter = payload[5]
        return f"end_stat_counter type=0x{stat_type:02x} counter=0x{counter:02x} raw={h}"

    if h == "3e0100":
        return "end_stat_terminal"

    return f"unknown raw={h}"


async def wait_for_target(
    addresses: List[str],
    timeout_s: int,
    scan_window_s: float,
    name_contains: str,
) -> TargetDevice:
    wanted = {a.lower() for a in addresses}
    start = time.time()
    name_filter = name_contains.lower().strip()

    if wanted:
        print(f"[scan] waiting for target devices: {', '.join(addresses)}")
    else:
        mode = f"name contains '{name_filter}'" if name_filter else "first discovered device"
        print(f"[scan] waiting for target device by {mode}")
    print(f"[scan] timeout={timeout_s}s, scan_window={scan_window_s}s")

    while True:
        devices = await BleakScanner.discover(timeout=scan_window_s)
        now = time.time()
        seen = {d.address.lower(): d for d in devices if d.address}

        print(f"[scan] found {len(devices)} devices")
        for d in devices:
            print(f"[scan]   - {d.address} name={d.name!r} rssi={getattr(d, 'rssi', None)}")

        for addr in wanted:
            if addr in seen:
                d = seen[addr]
                print(f"[scan] matched target {d.address} ({d.name})")
                return TargetDevice(name=d.name or "unknown", address=d.address)

        if not wanted:
            for d in devices:
                if not d.address:
                    continue
                dev_name = (d.name or "").lower()
                if name_filter and name_filter not in dev_name:
                    continue
                print(f"[scan] selected discovered device {d.address} ({d.name})")
                return TargetDevice(name=d.name or "unknown", address=d.address)

        if timeout_s > 0 and (now - start) >= timeout_s:
            raise TimeoutError("timed out waiting for target device")


def find_char_by_handle(client: BleakClient, handle: int):
    if client.services is None:
        return None

    for service in client.services:
        for char in service.characteristics:
            if char.handle == handle:
                return char
    return None


async def pair_if_requested(client: BleakClient, enabled: bool) -> None:
    if not enabled:
        print("[pair] pairing disabled by CLI")
        return

    if not hasattr(client, "pair"):
        print("[pair] client backend has no pair() method")
        return

    print("[pair] requesting OS-level pairing...")
    try:
        ok = await client.pair()
        print(f"[pair] pair() returned: {ok}")
    except NotImplementedError:
        print("[pair] pair() not implemented on this platform/backend")
    except Exception as exc:
        print(f"[pair] pairing failed: {exc}")


async def run(args: argparse.Namespace) -> None:
    _ = load_protocol(Path(args.protocol))

    if args.address:
        targets = [a.strip() for a in args.address.split(",") if a.strip()]
    else:
        targets = []

    target = await wait_for_target(
        addresses=targets,
        timeout_s=args.wait_timeout,
        scan_window_s=args.scan_window,
        name_contains=args.name_contains,
    )

    print(f"[connect] connecting to {target.address} ({target.name})")
    async with BleakClient(target.address, timeout=args.connect_timeout) as client:
        print(f"[connect] connected={client.is_connected}")
        await pair_if_requested(client, enabled=args.pair)

        notify_handle = parse_int_hex(args.notify_handle)
        write_handle = parse_int_hex(args.write_handle)

        notify_char = find_char_by_handle(client, notify_handle)
        write_char = find_char_by_handle(client, write_handle)

        if notify_char is None:
            raise RuntimeError(f"notify characteristic with handle {args.notify_handle} not found")
        if write_char is None:
            raise RuntimeError(f"write characteristic with handle {args.write_handle} not found")

        print(f"[char] notify handle={notify_char.handle} uuid={notify_char.uuid}")
        print(f"[char] write  handle={write_char.handle} uuid={write_char.uuid}")

        def on_notify(_: int, data: bytearray) -> None:
            payload = bytes(data)
            print(f"[notify] raw={hex_bytes(payload)} decoded={decode_notification(payload)}")

        await client.start_notify(notify_char, on_notify)
        print("[notify] notifications enabled")

        if args.send_startup:
            # Startup query (35)
            b1 = bytes.fromhex("35")
            print(f"[write] -> {write_char.handle:#06x} {b1.hex()} (startup query)")
            await client.write_gatt_char(write_char, b1, response=False)

            await asyncio.sleep(args.post_startup_delay)

            # Initial volume set (5bXX)
            volume = max(0, min(31, args.startup_volume))
            b2 = bytes([0x5B, volume])
            print(f"[write] -> {write_char.handle:#06x} {b2.hex()} (startup volume)")
            await client.write_gatt_char(write_char, b2, response=False)

            if args.send_poll:
                b3 = bytes.fromhex("51")
                print(f"[write] -> {write_char.handle:#06x} {b3.hex()} (status poll)")
                await client.write_gatt_char(write_char, b3, response=False)

        print(f"[run] listening for {args.listen_seconds}s (Ctrl+C to stop)")
        try:
            await asyncio.sleep(args.listen_seconds)
        except asyncio.CancelledError:
            pass
        finally:
            await client.stop_notify(notify_char)
            print("[notify] notifications disabled")


def build_parser() -> argparse.ArgumentParser:
    here = Path(__file__).resolve().parent
    default_protocol = here / "protocol_definition.json"

    p = argparse.ArgumentParser(description="LaserOps BLE protocol example client")
    p.add_argument("--protocol", default=str(default_protocol), help="path to protocol_definition.json")
    p.add_argument(
        "--address",
        default="",
        help="comma-separated BLE MAC addresses to wait for; optional",
    )
    p.add_argument(
        "--name-contains",
        default="",
        help="if --address is omitted, select first device whose name contains this text",
    )
    p.add_argument("--wait-timeout", type=int, default=0, help="seconds to wait for target device(s), 0=infinite")
    p.add_argument("--scan-window", type=float, default=3.0, help="seconds per scan round")
    p.add_argument("--connect-timeout", type=float, default=20.0, help="connect timeout in seconds")
    p.add_argument("--pair", action="store_true", help="attempt pairing after connect")

    p.add_argument("--notify-handle", default="0x0023", help="notification handle (hex)")
    p.add_argument("--write-handle", default="0x0026", help="write handle (hex)")

    p.add_argument("--send-startup", action="store_true", help="send startup writes (35 and 5bXX)")
    p.add_argument("--startup-volume", type=int, default=0, help="startup volume value 0..31 for 5bXX")
    p.add_argument("--post-startup-delay", type=float, default=0.2, help="delay between startup writes")
    p.add_argument("--send-poll", action="store_true", help="send one status poll (51) after startup writes")

    p.add_argument("--listen-seconds", type=float, default=30.0, help="how long to listen to notifications")
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    stop_event = asyncio.Event()

    def _handle_sigint(*_):
        print("\n[signal] interrupt received, shutting down...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_sigint)
        except NotImplementedError:
            pass

    async def _runner():
        task = asyncio.create_task(run(args))
        stopper = asyncio.create_task(stop_event.wait())
        done, pending = await asyncio.wait({task, stopper}, return_when=asyncio.FIRST_COMPLETED)
        for p in pending:
            p.cancel()
        for d in done:
            if d is task:
                await d

    try:
        loop.run_until_complete(_runner())
        return 0
    except Exception as exc:
        print(f"[error] {exc}")
        return 1
    finally:
        loop.close()


if __name__ == "__main__":
    sys.exit(main())
