#!/usr/bin/env python3
"""
Filter and anonymize BTSnoop HCI logs for repository sharing.

This script produces a filtered BTSnoop log that keeps:
    - every non-ACL frame
    - only ACL frames whose src/dst address matches one of the NerfV blaster
        addresses auto-discovered from the raw capture
    - then removes any packet that still references non-NerfV/non-phone devices

It then anonymizes Bluetooth MAC addresses in the resulting binary capture.

Default fake mapping scheme:
    - phone host: aa:aa:aa:aa:aa:aa
    - NerfV devices, in discovery order: bb:bb:bb:bb:bb:01, :02, ...
    - any other discovered Bluetooth addresses: cc:cc:cc:cc:cc:01, :02, ...

Important safety rule:
    - the all-zero address 00:00:00:00:00:00 is never rewritten, because this
        byte pattern can appear in non-address fields.

Typical usage:
  python scripts/anonymize_btsnoop.py \
      --input test_on_android/test_8/btsnoop_hci.log \
      --output test_on_android/test_8/filtered_.log \
      --force
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path


NERFV_NAME = "NerfV"
NERFV_SERVICE_UUID = "073e1435-85d1-455c-97cd-0b8262f20eac"
PHONE_FAKE = "aa:aa:aa:aa:aa:aa"
GUN_FAKE_PREFIX = "bb:bb:bb:bb:bb"
OTHER_FAKE_PREFIX = "cc:cc:cc:cc:cc"
ALL_ZERO_MAC = "00:00:00:00:00:00"
MAC_RE = re.compile(r"(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}")


def run_command(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=check,
        capture_output=True,
        env={**os.environ, "HOME": "/tmp"},
        text=True,
    )


def require_tshark() -> None:
    if shutil.which("tshark") is None:
        raise SystemExit("tshark is required but was not found in PATH")


def discover_nerfv_addresses(input_path: Path) -> list[str]:
    """Discover NerfV device addresses by searching for 'NerfV' string in ATT responses.
    
    Finds devices that respond with 'NerfV' in their device name characteristic
    during GATT service discovery.
    """
    candidates: list[str] = []
    
    # Extract all ATT packets and look for "NerfV" string responses
    result = run_command([
        "tshark", "-r", str(input_path),
        "-Y", "btatt",
        "-T", "text",
    ], check=False)
    
    if result.returncode in (0, 1):
        current_mac = None
        for line in result.stdout.splitlines():
            # Extract MAC address from Bluetooth packet headers
            if "→" in line or "← " in line:  # Packet direction indicators
                mac_match = MAC_RE.search(line)
                if mac_match:
                    current_mac = mac_match.group(0).lower()
            
            # Look for "NerfV" in ATT data
            if "NerfV" in line and current_mac:
                candidates.append(current_mac)

    # Deduplicate while preserving order
    deduped: list[str] = []
    seen: set[str] = set()
    for mac in candidates:
        if mac not in seen:
            seen.add(mac)
            deduped.append(mac)
    return deduped


def filter_capture(input_path: Path, output_path: Path, nerfv_addresses: list[str]) -> str:
    """Filter capture to include non-ACL packets and ACL traffic involving NerfV devices."""
    acl_terms: list[str] = []
    for address in nerfv_addresses:
        acl_terms.append(f"(bthci_acl.src.bd_addr == {address})")
        acl_terms.append(f"(bthci_acl.dst.bd_addr == {address})")
    
    if not acl_terms:
        # No NerfV devices: keep all non-ACL traffic
        display_filter = "!bthci_acl"
    else:
        joined = " || ".join(acl_terms)
        display_filter = f"(!bthci_acl) || ({joined})"
    
    run_command([
        "tshark",
        "-r", str(input_path),
        "-Y", display_filter,
        "-w", str(output_path),
    ])
    return display_filter


def discover_all_addresses(capture_path: Path) -> list[str]:
    """Extract every printable Bluetooth address from tshark's verbose decode."""
    result = run_command([
        "tshark",
        "-r", str(capture_path),
        "-V",
    ], check=False)
    if result.returncode not in (0, 1):
        raise SystemExit(result.stderr.strip() or "failed to inspect capture")

    addresses: list[str] = []
    seen: set[str] = set()
    for mac in MAC_RE.findall(result.stdout):
        lower = mac.lower()
        if lower not in seen:
            seen.add(lower)
            addresses.append(lower)
    return addresses


def infer_phone_address(capture_path: Path, nerfv_addresses: list[str]) -> str | None:
    result = run_command([
        "tshark",
        "-r", str(capture_path),
        "-T", "fields",
        "-e", "bthci_acl.src.bd_addr",
        "-e", "bthci_acl.dst.bd_addr",
        "-e", "btatt.opcode",
        "-E", "separator=|",
    ], check=False)
    if result.returncode not in (0, 1):
        return None

    counts: Counter[str] = Counter()
    nerfv_set = set(nerfv_addresses)
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) < 3 or not parts[2]:
            continue
        for mac in parts[:2]:
            lower = mac.strip().lower()
            if MAC_RE.fullmatch(lower) and lower not in nerfv_set:
                counts[lower] += 1
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def fake_mac(prefix: str, index: int) -> str:
    return f"{prefix}:{index:02x}"


def build_mapping(
    all_addresses: list[str],
    nerfv_addresses: list[str],
    phone_address: str | None,
) -> dict[str, str]:
    mapping: dict[str, str] = {}

    if phone_address:
        mapping[phone_address] = PHONE_FAKE

    for index, address in enumerate(nerfv_addresses, start=1):
        mapping[address] = fake_mac(GUN_FAKE_PREFIX, index)

    other_index = 1
    for address in all_addresses:
        if address == ALL_ZERO_MAC:
            continue
        if address in mapping:
            continue
        mapping[address] = fake_mac(OTHER_FAKE_PREFIX, other_index)
        other_index += 1

    return mapping


def mac_to_bytes(mac: str) -> bytes:
    return bytes.fromhex(mac.replace(":", ""))


def keep_acl_only_for_addresses(
    input_path: Path,
    output_path: Path,
    allowed_addresses: list[str],
    excluded_addresses: list[str],
) -> str:
    """Keep non-ACL + allowed ACL packets, excluding packets tied to other devices."""
    if not allowed_addresses:
        # Without known ACL endpoints, keep only non-ACL packets.
        acl_allow = "!bthci_acl"
    else:
        src_terms = " || ".join(
            f"(bthci_acl.src.bd_addr == {address})" for address in allowed_addresses
        )
        dst_terms = " || ".join(
            f"(bthci_acl.dst.bd_addr == {address})" for address in allowed_addresses
        )
        acl_allow = f"(!bthci_acl) || (({src_terms}) && ({dst_terms}))"

    if not excluded_addresses:
        display_filter = acl_allow
    else:
        # Common Bluetooth address fields seen in Android btsnoop captures.
        exclusion_fields = [
            "bthci_acl.src.bd_addr",
            "bthci_acl.dst.bd_addr",
            "bthci_cmd.bd_addr",
            "bthci_evt.bd_addr",
            "bthci_evt.direct_bd_addr",
            "btcommon.eir_ad.entry.bd_addr",
            "btle.central_bd_addr",
            "btle.peripheral_bd_addr",
        ]
        exclusion_terms: list[str] = []
        for address in excluded_addresses:
            for field in exclusion_fields:
                exclusion_terms.append(f"({field} == {address})")
        exclusion_filter = " || ".join(exclusion_terms)
        display_filter = f"({acl_allow}) && !({exclusion_filter})"

    run_command([
        "tshark",
        "-r", str(input_path),
        "-Y", display_filter,
        "-w", str(output_path),
    ])
    return display_filter


def anonymize_capture(input_path: Path, output_path: Path, mapping: dict[str, str]) -> None:
    data = input_path.read_bytes()
    for real_mac, fake_mac_value in mapping.items():
        if real_mac == ALL_ZERO_MAC:
            continue
        real_forward = mac_to_bytes(real_mac)
        real_reverse = real_forward[::-1]
        fake_forward = mac_to_bytes(fake_mac_value)
        fake_reverse = fake_forward[::-1]
        data = data.replace(real_forward, fake_forward)
        data = data.replace(real_reverse, fake_reverse)
    output_path.write_bytes(data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Filter and anonymize BTSnoop HCI logs")
    parser.add_argument("--input", required=True, help="Input BTSnoop HCI log")
    parser.add_argument("--output", required=True, help="Output filtered/anonymized BTSnoop log")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    return parser.parse_args()


def main() -> int:
    require_tshark()
    args = parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        raise SystemExit(f"input file not found: {input_path}")
    if output_path.exists() and not args.force:
        raise SystemExit(f"output file exists: {output_path} (use --force to overwrite)")

    with tempfile.TemporaryDirectory(prefix="laserops_sanitize_") as temp_dir:
        temp_dir_path = Path(temp_dir)
        staged_input_path = temp_dir_path / input_path.name
        filtered_path = temp_dir_path / "filtered.btsnoop"
        cleaned_path = temp_dir_path / "filtered_without_other_devices.btsnoop"
        shutil.copy2(input_path, staged_input_path)

        nerfv_addresses = discover_nerfv_addresses(staged_input_path)
        if not nerfv_addresses:
            raise SystemExit(
                "could not auto-discover NerfV devices (no devices named 'NerfV' with ACL traffic found)"
            )

        filtered_display = filter_capture(staged_input_path, filtered_path, nerfv_addresses)

        phone_address = infer_phone_address(filtered_path, nerfv_addresses)
        initially_seen_addresses = discover_all_addresses(filtered_path)
        other_addresses = [
            address
            for address in initially_seen_addresses
            if address not in nerfv_addresses
            and address != phone_address
            and address != ALL_ZERO_MAC
        ]

        allowed_acl_addresses = list(nerfv_addresses)
        if phone_address:
            allowed_acl_addresses.append(phone_address)
        pruning_display = keep_acl_only_for_addresses(
            filtered_path,
            cleaned_path,
            allowed_acl_addresses,
            other_addresses,
        )

        all_addresses = discover_all_addresses(cleaned_path)
        mapping = build_mapping(all_addresses, nerfv_addresses, phone_address)
        anonymize_capture(cleaned_path, output_path, mapping)

    print(f"Applied display filter for {len(nerfv_addresses)} NerfV device(s)")
    print("Applied secondary ACL pruning to keep only phone/NerfV endpoints")
    print(f"secondary_filter: {pruning_display}")
    if phone_address:
        print(f"phone_host -> {mapping[phone_address]}")
    else:
        print("phone_host: not inferred")
    for index, address in enumerate(nerfv_addresses):
        print(f"gun_{index} -> {mapping[address]}")
    other_index = 1
    for address in all_addresses:
        if address in nerfv_addresses or address == phone_address or address == ALL_ZERO_MAC:
            continue
        print(f"other_{other_index} -> {mapping[address]}")
        other_index += 1

    return 0


if __name__ == "__main__":
    sys.exit(main())