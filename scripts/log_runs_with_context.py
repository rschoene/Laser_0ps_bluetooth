#!/usr/bin/env python3
"""
Print a run-by-run ATT log with context, grouped into non-game and game phases.

This parser reads BTSnoop captures directly, without tshark, and formats the
messages in a compact log style similar to find_att_prefix_with_context.py.

Output structure per run:
  - non-game: menu/setup traffic before the game startup snapshot
  - game:
      - game-startup: startup snapshot and early setup traffic
      - gameplay: in-round traffic
      - finalization: end-of-round / end-of-game traffic

Direction coloring:
  - host -> device: red
  - device -> host: green

Examples:
  scripts/venv/bin/python scripts/log_runs_with_context.py \
    --paths test_on_android/test_13/filtered_.log

  scripts/venv/bin/python scripts/log_runs_with_context.py \
    --root test_on_android --glob '**/filtered_.log'
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import struct
import sys
import signal
from dataclasses import dataclass
from pathlib import Path


ATT_CID = 0x0004
PCAPNG_MAGIC = b"\x0a\x0d\x0d\x0a"
CORE_GAME_HANDLES = {0x0023, 0x0026}
CORE_SEGMENTATION_OPS = {0x1B, 0x52}
FINALIZATION_PRELUDE_US = 1_000_000


@dataclass
class AttMessage:
    file: Path
    rec_index: int
    ts_us: int
    flags: int
    conn_handle: int
    peer: str
    att_opcode: int
    att_handle: int | None
    value: bytes


@dataclass
class RunSlice:
    non_game: list[AttMessage]
    game_startup: list[AttMessage]
    gameplay: list[AttMessage]
    finalization: list[AttMessage]


class Ansi:
    RED = "\033[31m"
    GREEN = "\033[32m"
    DIM = "\033[2m"
    RESET = "\033[0m"


@dataclass
class MessageDefinition:
    prefix: bytes
    direction: str
    text: str
    fields: list[dict]
    outputs: list[dict]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
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
        default="**/filtered_.log",
        help="Recursive glob under --root (default: **/filtered_.log).",
    )
    parser.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
        help="Color mode for terminal output (default: auto).",
    )
    parser.add_argument(
        "--describe",
        action="store_true",
        help="Append known message meaning from protocol definition JSON.",
    )
    parser.add_argument(
        "--describe-detailed",
        action="store_true",
        help=(
            "Append known meaning plus decoded field values from protocol definition "
            "(implies --describe)."
        ),
    )
    parser.add_argument(
        "--hide-status-requests",
        action="store_true",
        help="Hide host->device status poll messages (0x51).",
    )
    parser.add_argument(
        "--hide-status-replies",
        action="store_true",
        help="Hide device->host status reply messages (0x51 XX YY).",
    )
    parser.add_argument(
        "--hide-status",
        action="store_true",
        help="Hide both status requests and status replies (all 0x51 traffic).",
    )
    parser.add_argument(
        "--hide-trigger",
        action="store_true",
        help="Hide device->host trigger/fire events (0x49).",
    )
    parser.add_argument(
        "--hide-reload-a",
        action="store_true",
        help="Hide device->host reload marker A events (0x52).",
    )
    parser.add_argument(
        "--hide-reload-b",
        action="store_true",
        help="Hide device->host reload marker B events (0x31xx).",
    )
    parser.add_argument(
        "--hide-reload",
        action="store_true",
        help="Hide both reload marker A and B events.",
    )
    parser.add_argument(
        "--hide-ammo-state",
        action="store_true",
        help="Hide device->host ammo state messages (0x32xx).",
    )
    parser.add_argument(
        "--hide-handles",
        nargs="*",
        default=[],
        help=(
            "Hide traffic for specific ATT handles (hex or decimal), "
            "for example: --hide-handles 0x0024 0x0001"
        ),
    )
    parser.add_argument(
        "--protocol-definition",
        default=str(
            (Path(__file__).resolve().parent.parent / "definition_protocol" / "protocol_definition.json")
        ),
        help=(
            "Path to protocol definition JSON "
            "(default: ../definition_protocol/protocol_definition.json)."
        ),
    )
    return parser.parse_args()


def iter_input_files(paths: list[str], root: str, pattern: str) -> list[Path]:
    if paths:
        files = [Path(p) for p in paths]
    else:
        base = Path(root)
        files = [Path(p) for p in glob.glob(str(base / pattern), recursive=True)]
    return sorted(p for p in files if p.is_file())


def color_enabled(mode: str) -> bool:
    if mode == "always":
        return True
    if mode == "never":
        return False
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def red(text: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{Ansi.RED}{text}{Ansi.RESET}"


def green(text: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{Ansi.GREEN}{text}{Ansi.RESET}"


def dim(text: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{Ansi.DIM}{text}{Ansi.RESET}"


def fmt_direction(flags: int) -> tuple[str, str, bool]:
    # btsnoop flag bit0: 0=sent from the logger point-of-view, 1=received.
    if flags & 0x01:
        return ("device", "host", True)
    return ("host", "device", False)


def normalize_hex(raw: str) -> bytes | None:
    hex_str = raw.strip().lower().replace("0x", "").replace(" ", "")
    if not hex_str:
        return None
    if len(hex_str) % 2 != 0:
        return None
    try:
        return bytes.fromhex(hex_str)
    except ValueError:
        return None


def parse_handle(value: str) -> int:
    text = value.strip().lower()
    if text.startswith("0x"):
        return int(text, 16)
    return int(text, 10)


def load_message_definitions(path: Path) -> list[MessageDefinition]:
    data = json.loads(path.read_text(encoding="utf-8"))
    messages = data.get("messages", {})
    definitions: list[MessageDefinition] = []

    for name, msg in messages.items():
        if not isinstance(msg, dict):
            continue

        direction = msg.get("direction", "bidirectional")
        prefix_raw = msg.get("id_hex_prefix") or msg.get("id_hex")
        if not isinstance(prefix_raw, str):
            continue
        prefix = normalize_hex(prefix_raw)
        if not prefix:
            continue

        desc = msg.get("description")
        if not isinstance(desc, str) or not desc.strip():
            desc = msg.get("semantics")
        if not isinstance(desc, str) or not desc.strip():
            desc = msg.get("meaning")
        if not isinstance(desc, str) or not desc.strip():
            desc = name.replace("_", " ")

        fields = msg.get("fields")
        if not isinstance(fields, list):
            fields = []

        outputs = msg.get("outputs")
        if not isinstance(outputs, list):
            outputs = []

        definitions.append(
            MessageDefinition(
                prefix=prefix,
                direction=direction,
                text=desc.strip(),
                fields=fields,
                outputs=outputs,
            )
        )

    # Prefer the most specific prefix if multiple definitions match.
    definitions.sort(key=lambda d: len(d.prefix), reverse=True)
    return definitions


def describe_message(m: AttMessage, definitions: list[MessageDefinition]) -> str | None:
    if not m.value or not definitions:
        return None

    is_host_to_device = (m.flags & 0x01) == 0

    msg_direction = "host_to_gun" if is_host_to_device else "gun_to_host"

    for d in definitions:
        if not m.value.startswith(d.prefix):
            continue
        if d.direction in ("bidirectional", msg_direction):
            return d.text

    return None


def matching_definition(m: AttMessage, definitions: list[MessageDefinition]) -> MessageDefinition | None:
    if not m.value or not definitions:
        return None

    is_host_to_device = (m.flags & 0x01) == 0
    msg_direction = "host_to_gun" if is_host_to_device else "gun_to_host"

    for d in definitions:
        if not m.value.startswith(d.prefix):
            continue
        if d.direction in ("bidirectional", msg_direction):
            return d
    return None


def detailed_description(m: AttMessage, definitions: list[MessageDefinition]) -> str | None:
    d = matching_definition(m, definitions)
    if d is None:
        return None

    details: list[str] = []
    for raw_field in d.fields:
        if not isinstance(raw_field, dict):
            continue

        name = raw_field.get("name")
        if not isinstance(name, str) or not name.strip():
            continue

        index = raw_field.get("index")
        indexes = raw_field.get("indexes")

        if isinstance(index, int):
            if 0 <= index < len(m.value):
                b = m.value[index]
                details.append(f"{name}=0x{b:02x}({b})")
            continue

        if isinstance(indexes, list) and indexes and all(isinstance(i, int) for i in indexes):
            if all(0 <= i < len(m.value) for i in indexes):
                bs = bytes(m.value[i] for i in indexes)
                n = int.from_bytes(bs, "big")
                details.append(f"{name}=0x{bs.hex()}({n})")

    for raw_output in d.outputs:
        if not isinstance(raw_output, dict):
            continue

        out_desc = raw_output.get("description")
        if not isinstance(out_desc, str) or not out_desc.strip():
            continue

        value_raw = raw_output.get("value_hex")
        if isinstance(value_raw, str):
            value = normalize_hex(value_raw)
            if value is not None and m.value == value:
                details.append(f"output={out_desc.strip()}")
                continue

        prefix_raw = raw_output.get("prefix_hex")
        if isinstance(prefix_raw, str):
            prefix = normalize_hex(prefix_raw)
            if prefix is not None and m.value.startswith(prefix):
                details.append(f"output={out_desc.strip()}")

    if not details:
        return d.text
    return f"{d.text} | " + ", ".join(details)


def fmt_message(
    m: AttMessage,
    first_ts_us: int,
    use_color: bool,
    describe: bool,
    describe_detailed: bool,
    definitions: list[MessageDefinition],
) -> str:
    src, dst, is_rx = fmt_direction(m.flags)
    rel_s = (m.ts_us - first_ts_us) / 1_000_000.0
    handle = "-" if m.att_handle is None else f"0x{m.att_handle:04x}"
    line = f"{rel_s:10.6f}s: {src} -> {dst} ({handle}) {m.value.hex()}"
    if describe_detailed:
        meaning = detailed_description(m, definitions)
        if meaning:
            line = f"{line}  ; {meaning}"
    elif describe:
        meaning = describe_message(m, definitions)
        if meaning:
            line = f"{line}  ; {meaning}"
    if not use_color:
        return line
    return green(line, True) if is_rx else red(line, True)


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
        if not pkt or pkt[0] != 0x02 or len(pkt) < 9:
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
        att_handle: int | None = None
        value = b""
        if len(att) >= 3:
            att_handle = struct.unpack_from("<H", att, 1)[0]
            value = att[3:]
        elif len(att) >= 2:
            value = att[1:]

        messages.append(
            AttMessage(
                file=path,
                rec_index=rec_idx,
                ts_us=ts_us,
                flags=flags,
                conn_handle=conn_handle,
                peer=f"conn:0x{conn_handle:04x}",
                att_opcode=att_opcode,
                att_handle=att_handle,
                value=value,
            )
        )

    return messages


def split_run(messages: list[AttMessage]) -> RunSlice:
    relevant = list(messages)
    core = [
        m
        for m in relevant
        if m.att_handle in CORE_GAME_HANDLES and m.att_opcode in CORE_SEGMENTATION_OPS
    ]
    if not relevant or not core:
        return RunSlice([], [], [], [])

    def is_host_to_device(m: AttMessage) -> bool:
        return (m.flags & 0x01) == 0

    def is_device_to_host(m: AttMessage) -> bool:
        return (m.flags & 0x01) == 1

    # Start of a run's game phase: setup writes after menu/navigation.
    game_start_markers = {0x44, 0x49, 0x36, 0x4A, 0x41}
    game_start_index = next(
        (
            i
            for i, m in enumerate(core)
            if is_host_to_device(m) and m.value and m.value[0] in game_start_markers
        ),
        None,
    )
    if game_start_index is None:
        return RunSlice(relevant, [], [], [])

    game_start_rec = core[game_start_index].rec_index
    game = core[game_start_index:]

    # Gameplay begins when action traffic appears (trigger/ammo/reload), not setup writes.
    gameplay_start = next(
        (
            i
            for i, m in enumerate(game)
            if m.value
            and (
                (is_device_to_host(m) and m.value[0] in {0x49, 0x32, 0x52, 0x31, 0x47})
                or (is_host_to_device(m) and m.value[0] in {0x37, 0x58, 0x5A})
                or (is_device_to_host(m) and m.value.startswith(bytes.fromhex("30013f")))
            )
        ),
        len(game),
    )

    # Finalization starts when end-of-round/result traffic appears.
    # This supports both single-player (3e/42) and multiplayer (47/54/42).
    def is_finalization_marker(m: AttMessage) -> bool:
        if not m.value:
            return False
        first = m.value[0]
        if is_host_to_device(m) and first in {0x54, 0x42}:
            return True
        if is_device_to_host(m) and first in {0x47, 0x54, 0x3E}:
            return True
        return False

    finalization_start = next(
        (i for i in range(gameplay_start, len(game)) if is_finalization_marker(game[i])),
        len(game),
    )

    gameplay_rec = game[gameplay_start].rec_index if gameplay_start < len(game) else None
    finalization_rec = game[finalization_start].rec_index if finalization_start < len(game) else None
    finalization_ts = game[finalization_start].ts_us if finalization_start < len(game) else None

    non_game: list[AttMessage] = []
    game_startup: list[AttMessage] = []
    gameplay: list[AttMessage] = []
    finalization: list[AttMessage] = []

    for m in relevant:
        if m.rec_index < game_start_rec:
            non_game.append(m)
            continue

        if gameplay_rec is None:
            game_startup.append(m)
            continue

        if m.rec_index < gameplay_rec:
            game_startup.append(m)
            continue

        if finalization_rec is None:
            gameplay.append(m)
            continue

        if m.rec_index >= finalization_rec:
            finalization.append(m)
            continue

        # Pull short, non-core control bursts right before final markers into
        # finalization. This keeps end-of-round control chatter (for example
        # setup writes/discovery traffic immediately before 47/54/42) out of
        # gameplay without shifting the core marker boundaries.
        is_core_msg = (
            m.att_handle in CORE_GAME_HANDLES and m.att_opcode in CORE_SEGMENTATION_OPS
        )
        if (
            not is_core_msg
            and finalization_ts is not None
            and m.ts_us >= (finalization_ts - FINALIZATION_PRELUDE_US)
        ):
            finalization.append(m)
        else:
            gameplay.append(m)

    return RunSlice(non_game, game_startup, gameplay, finalization)


def print_section(
    title: str,
    messages: list[AttMessage],
    first_ts_us: int,
    use_color: bool,
    describe: bool,
    describe_detailed: bool,
    definitions: list[MessageDefinition],
    hide_status_requests: bool,
    hide_status_replies: bool,
    hide_trigger: bool,
    hide_reload_a: bool,
    hide_reload_b: bool,
    hide_ammo_state: bool,
    hide_handles: set[int],
    indent: str = "",
) -> None:
    print(f"{indent}{title}")
    filtered = messages
    if hide_handles:
        filtered = [
            m
            for m in filtered
            if not (m.att_handle is not None and m.att_handle in hide_handles)
        ]

    if hide_status_requests or hide_status_replies:
        filtered = [
            m
            for m in filtered
            if not (
                len(m.value) >= 1
                and m.value[0] == 0x51
                and (
                    ((m.flags & 0x01) == 0 and hide_status_requests)
                    or ((m.flags & 0x01) == 1 and hide_status_replies)
                )
            )
        ]

    if hide_trigger:
        filtered = [
            m
            for m in filtered
            if not (
                (m.flags & 0x01) == 1
                and len(m.value) == 1
                and m.value[0] == 0x49
            )
        ]

    if hide_reload_a:
        filtered = [
            m
            for m in filtered
            if not (
                (m.flags & 0x01) == 1
                and len(m.value) == 1
                and m.value[0] == 0x52
            )
        ]

    if hide_reload_b:
        filtered = [
            m
            for m in filtered
            if not (
                (m.flags & 0x01) == 1
                and len(m.value) >= 1
                and m.value[0] == 0x31
            )
        ]

    if hide_ammo_state:
        filtered = [
            m
            for m in filtered
            if not (
                (m.flags & 0x01) == 1
                and len(m.value) >= 1
                and m.value[0] == 0x32
            )
        ]

    if not filtered:
        print(f"{indent}  {dim('(no messages)', use_color)}")
        return
    for m in filtered:
        print(
            f"{indent}  "
            f"{fmt_message(m, first_ts_us, use_color, describe, describe_detailed, definitions)}"
        )


def print_run(
    path: Path,
    run_number: int,
    run: RunSlice,
    file_first_ts_us: int,
    use_color: bool,
    describe: bool,
    describe_detailed: bool,
    definitions: list[MessageDefinition],
    hide_status_requests: bool,
    hide_status_replies: bool,
    hide_trigger: bool,
    hide_reload_a: bool,
    hide_reload_b: bool,
    hide_ammo_state: bool,
    hide_handles: set[int],
) -> None:
    all_messages = run.non_game + run.game_startup + run.gameplay + run.finalization
    if not all_messages:
        return

    print(f"\n=== {path} :: run {run_number} ===")
    print_section(
        "non-game",
        run.non_game,
        file_first_ts_us,
        use_color,
        describe,
        describe_detailed,
        definitions,
        hide_status_requests,
        hide_status_replies,
        hide_trigger,
        hide_reload_a,
        hide_reload_b,
        hide_ammo_state,
        hide_handles,
    )
    print("game")
    print_section(
        "game-startup",
        run.game_startup,
        file_first_ts_us,
        use_color,
        describe,
        describe_detailed,
        definitions,
        hide_status_requests,
        hide_status_replies,
        hide_trigger,
        hide_reload_a,
        hide_reload_b,
        hide_ammo_state,
        hide_handles,
        indent="  ",
    )
    print_section(
        "gameplay",
        run.gameplay,
        file_first_ts_us,
        use_color,
        describe,
        describe_detailed,
        definitions,
        hide_status_requests,
        hide_status_replies,
        hide_trigger,
        hide_reload_a,
        hide_reload_b,
        hide_ammo_state,
        hide_handles,
        indent="  ",
    )
    print_section(
        "finalization",
        run.finalization,
        file_first_ts_us,
        use_color,
        describe,
        describe_detailed,
        definitions,
        hide_status_requests,
        hide_status_replies,
        hide_trigger,
        hide_reload_a,
        hide_reload_b,
        hide_ammo_state,
        hide_handles,
        indent="  ",
    )


def main() -> int:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    args = parse_args()
    files = iter_input_files(args.paths, args.root, args.glob)
    if not files:
        print("No input files found.")
        return 1

    use_color = color_enabled(args.color)
    describe = args.describe or args.describe_detailed
    hide_status_requests = args.hide_status_requests or args.hide_status
    hide_status_replies = args.hide_status_replies or args.hide_status
    hide_trigger = args.hide_trigger
    hide_reload_a = args.hide_reload_a or args.hide_reload
    hide_reload_b = args.hide_reload_b or args.hide_reload
    hide_ammo_state = args.hide_ammo_state
    try:
        hide_handles = {parse_handle(v) for v in args.hide_handles}
    except ValueError as exc:
        print(f"Invalid value in --hide-handles: {exc}")
        return 2

    definitions: list[MessageDefinition] = []
    if describe:
        definition_path = Path(args.protocol_definition)
        try:
            definitions = load_message_definitions(definition_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"Error loading protocol definition {definition_path}: {exc}")
            return 2

    total_runs = 0

    for path in files:
        try:
            messages = parse_att_messages(path)
        except ValueError as exc:
            print(f"\n=== {path} ===")
            print(f"Error: {exc}")
            continue

        relevant = list(messages)
        core_relevant = [
            m
            for m in relevant
            if m.att_handle in CORE_GAME_HANDLES and m.att_opcode in CORE_SEGMENTATION_OPS
        ]
        if not core_relevant:
            continue

        file_first_ts_us = min(m.ts_us for m in relevant)

        # Split into runs by explicit end marker host->device 0x42.
        run_chunks: list[list[AttMessage]] = []
        current: list[AttMessage] = []
        for m in core_relevant:
            current.append(m)
            if (m.flags & 0x01) == 0 and m.value and m.value[0] == 0x42:
                run_chunks.append(current)
                current = []
        if current:
            run_chunks.append(current)

        # Some captures contain stats tail + next game startup in one chunk
        # because no 0x42 appears between them. Split such chunks at a clear
        # restart point: long idle gap followed by assignment/startup traffic.
        def is_restart_marker(m: AttMessage) -> bool:
            if not m.value or (m.flags & 0x01) != 0:
                return False
            first = m.value[0]
            if first == 0x44:
                return True
            if first == 0x49 and len(m.value) >= 3:
                return True
            return False

        def has_nearby_game_config(chunk: list[AttMessage], start_idx: int, window: int = 30) -> bool:
            end = min(len(chunk), start_idx + window)
            for i in range(start_idx, end):
                m = chunk[i]
                if not m.value or (m.flags & 0x01) != 0:
                    continue
                if m.value[0] in {0x4A, 0x58}:
                    return True
            return False

        split_chunks: list[list[AttMessage]] = []
        idle_gap_us = 30_000_000
        for chunk in run_chunks:
            if len(chunk) < 2:
                split_chunks.append(chunk)
                continue

            start = 0
            for i in range(1, len(chunk)):
                prev = chunk[i - 1]
                cur = chunk[i]
                if (
                    (cur.ts_us - prev.ts_us) >= idle_gap_us
                    and is_restart_marker(cur)
                    and has_nearby_game_config(chunk, i)
                ):
                    split_chunks.append(chunk[start:i])
                    start = i
            split_chunks.append(chunk[start:])

        run_chunks = [c for c in split_chunks if c]

        # Merge trailing stats-only chunks back into the preceding gameplay run.
        # Multiplayer captures (e.g. test_8) can contain multiple 0x42 closes
        # while still finalizing one match (47/54 exchange), which otherwise
        # looks like many tiny runs.
        def has_startup_or_gameplay_markers(chunk: list[AttMessage]) -> bool:
            for m in chunk:
                if not m.value:
                    continue
                first = m.value[0]
                is_host = (m.flags & 0x01) == 0
                is_device = (m.flags & 0x01) == 1
                if is_host and first in {0x44, 0x4A, 0x58, 0x37, 0x5A}:
                    return True
                if is_device and first in {0x49, 0x32, 0x52, 0x31, 0x30}:
                    return True
            return False

        def is_tail_only_chunk(chunk: list[AttMessage]) -> bool:
            if not chunk:
                return False
            saw_tail = False
            for m in chunk:
                if not m.value:
                    continue
                first = m.value[0]
                # Allow status chatter inside tail chunks.
                if first in {0x51, 0x42, 0x54, 0x47}:
                    if first in {0x42, 0x54, 0x47}:
                        saw_tail = True
                    continue
                return False
            return saw_tail

        merged_chunks: list[list[AttMessage]] = []
        for chunk in run_chunks:
            if merged_chunks and is_tail_only_chunk(chunk) and has_startup_or_gameplay_markers(merged_chunks[-1]):
                merged_chunks[-1].extend(chunk)
            else:
                merged_chunks.append(chunk)
        run_chunks = merged_chunks

        # Expand core chunks back to full ATT traffic ranges for printing.
        expanded_chunks: list[list[AttMessage]] = []
        for chunk in run_chunks:
            if not chunk:
                continue
            start_rec = chunk[0].rec_index
            end_rec = chunk[-1].rec_index
            expanded = [m for m in relevant if start_rec <= m.rec_index <= end_rec]
            if expanded:
                expanded_chunks.append(expanded)
        run_chunks = expanded_chunks

        for run_number, chunk in enumerate(run_chunks, start=1):
            run = split_run(chunk)
            print_run(
                path,
                run_number,
                run,
                file_first_ts_us,
                use_color,
                describe,
                args.describe_detailed,
                definitions,
                hide_status_requests,
                hide_status_replies,
                hide_trigger,
                hide_reload_a,
                hide_reload_b,
                hide_ammo_state,
                hide_handles,
            )
            total_runs += 1

    print(f"\nTotal runs: {total_runs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())