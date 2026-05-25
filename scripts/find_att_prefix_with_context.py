#!/usr/bin/env python3
"""
Find ATT messages by value prefix and print peer-local context.

This tool parses btsnoop_hci.log files directly (no tshark required), searches
for ATT values that start with a user-provided hex prefix, and prints:
  - the matched message
  - N previous messages (default 2)
  - M next messages (default 5)
within the same peer conversation (same ACL connection handle, with best-effort
mapping to remote Bluetooth address when connection-complete events are present).

Examples:
  scripts/venv/bin/python scripts/find_att_prefix_with_context.py 4a

  scripts/venv/bin/python scripts/find_att_prefix_with_context.py 4a0000 \
    --root test_on_android --prev 3 --next 6

  scripts/venv/bin/python scripts/find_att_prefix_with_context.py 490100 \
    --paths test_on_android/test_2/btsnoop_hci.log
"""

from __future__ import annotations

import argparse
import glob
import os
import struct
import sys
from dataclasses import dataclass
from pathlib import Path


ATT_CID = 0x0004
PCAPNG_MAGIC = b"\x0a\x0d\x0d\x0a"

ATT_METHODS: dict[int, str] = {
    0x01: "Error Response",
    0x02: "Exchange MTU Request",
    0x03: "Exchange MTU Response",
    0x04: "Find Information Request",
    0x05: "Find Information Response",
    0x06: "Find By Type Value Request",
    0x07: "Find By Type Value Response",
    0x08: "Read By Type Request",
    0x09: "Read By Type Response",
    0x0A: "Read Request",
    0x0B: "Read Response",
    0x0C: "Read Blob Request",
    0x0D: "Read Blob Response",
    0x0E: "Read Multiple Request",
    0x0F: "Read Multiple Response",
    0x10: "Read By Group Type Request",
    0x11: "Read By Group Type Response",
    0x12: "Write Request",
    0x13: "Write Response",
    0x16: "Prepare Write Request",
    0x17: "Prepare Write Response",
    0x18: "Execute Write Request",
    0x19: "Execute Write Response",
    0x1B: "Handle Value Notification",
    0x1D: "Handle Value Indication",
    0x1E: "Handle Value Confirmation",
    0x52: "Write Command",
    0xD2: "Signed Write Command",
}

# Opcodes where ATT PDU includes a 16-bit handle followed by value bytes.
ATT_HANDLE_VALUE_OPS = {0x12, 0x1B, 0x1D, 0x52, 0xD2, 0x16, 0x17}


@dataclass
class AttMessage:
    file: Path
    rec_index: int
    ts_us: int
    flags: int
    conn_handle: int
    peer: str
    att_opcode: int
    att_method: str
    att_handle: int | None
    value: bytes


@dataclass
class Hit:
    message: AttMessage
    context: list[AttMessage]
    context_index: int


class Ansi:
    GREEN = "\033[32m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "prefix",
        help="Hex prefix to match at the start of ATT value (e.g. 4a, 490100).",
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        default=[],
        help="Optional explicit capture files. If omitted, --root/--glob is used.",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Root directory used with --glob (default: current directory).",
    )
    parser.add_argument(
        "--glob",
        default="**/btsnoop_hci.log",
        help="Recursive glob under --root (default: **/btsnoop_hci.log).",
    )
    parser.add_argument(
        "--prev",
        type=int,
        default=2,
        help="How many previous peer messages to print (default: 2).",
    )
    parser.add_argument(
        "--next",
        dest="next_count",
        type=int,
        default=5,
        help="How many next peer messages to print (default: 5).",
    )
    parser.add_argument(
        "--max-hits",
        type=int,
        default=0,
        help="Optional maximum hits to print per file (0 = all).",
    )
    parser.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
        help="Color mode for terminal output (default: auto).",
    )
    return parser.parse_args()


def normalize_hex_prefix(raw: str) -> bytes:
    hex_str = raw.strip().lower().replace("0x", "")
    if len(hex_str) == 0:
        raise ValueError("prefix must not be empty")
    if len(hex_str) % 2 != 0:
        raise ValueError("prefix must have an even number of hex chars")
    try:
        return bytes.fromhex(hex_str)
    except ValueError as exc:
        raise ValueError(f"invalid hex prefix: {raw}") from exc


def iter_input_files(paths: list[str], root: str, pattern: str) -> list[Path]:
    if paths:
        files = [Path(p) for p in paths]
    else:
        base = Path(root)
        files = [Path(p) for p in glob.glob(str(base / pattern), recursive=True)]
    return sorted(p for p in files if p.is_file())


def bdaddr_to_str(raw6: bytes) -> str:
    # Addresses in HCI events are little-endian on the wire.
    b = raw6[::-1]
    return ":".join(f"{x:02x}" for x in b)


def decode_hci_event_for_peer(pkt: bytes, handle_to_peer: dict[int, str]) -> None:
    # pkt includes H4 type byte at [0], event starts at [1].
    if len(pkt) < 3:
        return
    evt_code = pkt[1]
    plen = pkt[2]
    params = pkt[3 : 3 + plen]
    if len(params) < plen:
        return

    # Classic HCI Connection Complete Event (0x03)
    if evt_code == 0x03 and len(params) >= 11:
        status = params[0]
        if status == 0x00:
            handle = struct.unpack_from("<H", params, 1)[0] & 0x0FFF
            peer = bdaddr_to_str(params[3:9])
            handle_to_peer[handle] = peer
        return

    # LE Meta Event (0x3E): parse common LE connection-complete subevents.
    if evt_code == 0x3E and len(params) >= 2:
        subevent = params[0]
        # 0x01 LE Connection Complete
        if subevent == 0x01 and len(params) >= 19:
            status = params[1]
            if status == 0x00:
                handle = struct.unpack_from("<H", params, 2)[0] & 0x0FFF
                peer = bdaddr_to_str(params[5:11])
                handle_to_peer[handle] = peer
            return
        # 0x0A LE Enhanced Connection Complete
        if subevent == 0x0A and len(params) >= 31:
            status = params[1]
            if status == 0x00:
                handle = struct.unpack_from("<H", params, 2)[0] & 0x0FFF
                peer = bdaddr_to_str(params[6:12])
                handle_to_peer[handle] = peer
            return


def decode_att_value(att_payload: bytes, opcode: int) -> tuple[int | None, bytes | None]:
    if opcode in ATT_HANDLE_VALUE_OPS:
        if len(att_payload) < 3:
            return (None, None)
        att_handle = struct.unpack_from("<H", att_payload, 1)[0]
        return (att_handle, att_payload[3:])
    return (None, None)


def parse_att_messages(path: Path) -> list[AttMessage]:
    data = path.read_bytes()
    if len(data) < 16:
        raise ValueError(f"{path}: file too short to be a valid BTSnoop capture")
    if not data.startswith(b"btsnoop\x00"):
        if data.startswith(PCAPNG_MAGIC):
            raise ValueError(
                f"{path}: unsupported capture format (pcapng). "
                "This tool expects BTSnoop. Convert with: "
                f"tshark -r {path} -F btsnoop -w <output.btsnoop>"
            )
        raise ValueError(f"{path}: unsupported capture format (expected BTSnoop header)")

    messages: list[AttMessage] = []
    handle_to_peer: dict[int, str] = {}

    off = 16
    rec_idx = 0
    while off + 24 <= len(data):
        rec_idx += 1
        _, incl_len, flags, _, ts_us = struct.unpack_from(
            ">IIIIQ", data, off
        )
        off += 24
        if off + incl_len > len(data):
            break
        pkt = data[off : off + incl_len]
        off += incl_len
        if not pkt:
            continue

        h4_type = pkt[0]

        # Track connection-handle -> peer address using HCI events.
        if h4_type == 0x04:
            decode_hci_event_for_peer(pkt, handle_to_peer)
            continue

        # ACL Data packet
        if h4_type != 0x02 or len(pkt) < 9:
            continue

        hci_handle_flags = struct.unpack_from("<H", pkt, 1)[0]
        conn_handle = hci_handle_flags & 0x0FFF
        acl_data_len = struct.unpack_from("<H", pkt, 3)[0]
        acl_data = pkt[5 : 5 + acl_data_len]
        if len(acl_data) < 4:
            continue

        l2cap_len, l2cap_cid = struct.unpack_from("<HH", acl_data, 0)
        if l2cap_cid != ATT_CID:
            continue

        att = acl_data[4 : 4 + l2cap_len]
        if not att:
            continue

        att_opcode = att[0]
        att_method = ATT_METHODS.get(att_opcode, f"0x{att_opcode:02x}")
        att_handle, value = decode_att_value(att, att_opcode)
        if value is None:
            continue

        peer = handle_to_peer.get(conn_handle, f"conn:0x{conn_handle:04x}")
        messages.append(
            AttMessage(
                file=path,
                rec_index=rec_idx,
                ts_us=ts_us,
                flags=flags,
                conn_handle=conn_handle,
                peer=peer,
                att_opcode=att_opcode,
                att_method=att_method,
                att_handle=att_handle,
                value=value,
            )
        )

    return messages


def direction(flags: int) -> str:
    # btsnoop flag bit0: 0=sent, 1=received from the logger point-of-view.
    return "rx" if (flags & 0x01) else "tx"


def flow_endpoints(m: AttMessage) -> tuple[str, str]:
    # Local endpoint MAC is generally not present in ACL ATT frames directly.
    # Use a stable local label and the discovered peer address.
    local = "phone_host"
    if direction(m.flags) == "tx":
        return (local, m.peer)
    return (m.peer, local)


def collect_hits(
    messages: list[AttMessage],
    prefix: bytes,
    prev_count: int,
    next_count: int,
) -> list[Hit]:
    by_peer: dict[str, list[AttMessage]] = {}
    for m in messages:
        by_peer.setdefault(m.peer, []).append(m)

    rec_to_hit: list[Hit] = []
    for peer_msgs in by_peer.values():
        for idx, m in enumerate(peer_msgs):
            if m.value.startswith(prefix):
                lo = max(0, idx - prev_count)
                hi = min(len(peer_msgs), idx + next_count + 1)
                context = peer_msgs[lo:hi]
                context_idx = idx - lo
                rec_to_hit.append(Hit(message=m, context=context, context_index=context_idx))

    rec_to_hit.sort(key=lambda h: h.message.rec_index)
    return rec_to_hit


def fmt_message(m: AttMessage, first_ts_us: int) -> str:
    src, dst = flow_endpoints(m)
    # btsnoop timestamps are absolute; relative seconds are easier to read.
    rel_s = (m.ts_us - first_ts_us) / 1_000_000.0
    handle = "-" if m.att_handle is None else f"0x{m.att_handle:04x}"
    return (
        f"{rel_s:10.6f}s: {src} -> {dst} "
        f"({handle}) {m.value.hex()} ({m.att_method})"
    )


def color_enabled(mode: str) -> bool:
    if mode == "always":
        return True
    if mode == "never":
        return False
    # auto: color only on interactive terminals and when NO_COLOR is not set.
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def green(text: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{Ansi.GREEN}{text}{Ansi.RESET}"


def dim(text: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{Ansi.DIM}{text}{Ansi.RESET}"


def print_hits(path: Path, hits: list[Hit], max_hits: int, use_color: bool) -> int:
    print(f"\n=== {path} ===")
    if not hits:
        print(dim("(no matches)", use_color))
        return 0

    first_ts_us = min(h.message.ts_us for h in hits)

    shown = hits if max_hits <= 0 else hits[:max_hits]
    for i, h in enumerate(shown, start=1):
        print(f"\n-- hit {i}/{len(hits)} --")
        print("match:")
        print("  " + fmt_message(h.message, first_ts_us))
        print("context (same peer conversation):")
        for j, c in enumerate(h.context):
            marker = "*" if j == h.context_index else " "
            line = f" {marker} {fmt_message(c, first_ts_us)}"
            if j == h.context_index:
                print(green(line, use_color))
            else:
                print(line)

    if max_hits > 0 and len(hits) > max_hits:
        print(f"\n... truncated: showing {max_hits} of {len(hits)} hits")
    return len(hits)


def main() -> int:
    args = parse_args()
    try:
        prefix = normalize_hex_prefix(args.prefix)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 2

    files = iter_input_files(args.paths, args.root, args.glob)
    if not files:
        print("No input files found.")
        return 1

    use_color = color_enabled(args.color)

    total_hits = 0
    parse_errors = 0
    for path in files:
        try:
            messages = parse_att_messages(path)
        except ValueError as exc:
            print(f"\n=== {path} ===")
            print(f"Error: {exc}")
            parse_errors += 1
            continue
        hits = collect_hits(messages, prefix, args.prev, args.next_count)
        total_hits += print_hits(path, hits, args.max_hits, use_color)

    print(f"\nTotal matches: {total_hits}")
    if parse_errors:
        print(f"Files with parse errors: {parse_errors}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
