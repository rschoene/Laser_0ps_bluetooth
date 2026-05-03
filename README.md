# Laser_0ps_bluetooth

Reverse-engineering notes, test captures, and Python tooling for the BLE protocol used by LaserOps blasters.

## Project Goals

- Document the observed BLE protocol between app and blaster(s).
- Keep test runs reproducible and comparable across sessions.
- Provide machine-readable protocol definitions usable in Python.
- Provide a runnable BLE example with pairing, debug prints, and wait-for-device behavior.

## Repository Layout

- `definition_protocol/`
	- `protocol_definition.json`: machine-readable protocol model.
	- `example_ble_protocol_client.py`: BLE scanner/client example using Bleak.
	- `README.md`: usage instructions for the Python client.
- `test_on_android/`
	- `test_definition.md`: test plan definitions.
	- `devices.md`: sanitized replacement map for device addresses.
	- `test_1/` ... `test_7/`: per-test notes and `filtered_.log` exports.

## Current Protocol Status

The protocol is reverse-engineered and still evolving.

High-confidence items include:

- Transport direction and handles:
	- host writes typically on `0x0026`
	- gun notifications typically on `0x0023`
- Startup exchange (`35` query, `35...` snapshot, initial `5bxx` volume set).
- Config/state writes (`36...`) and persistent level byte behavior.
- Gameplay event families (`49`, `52` + `31xx`, `32xx`).
- End-stat flow (`5a3f...`, `30013f...`, `3e0100`, `42`).

See `test_on_android/test_1/traffic_definition.md` for detailed byte-level notes and confidence annotations.

## Python Usage

Install dependency:

```bash
pip install bleak
```

Run the example BLE client:

```bash
python definition_protocol/example_ble_protocol_client.py \
	--address <gun_0_address> \
	--pair \
	--send-startup \
	--startup-volume 0 \
	--send-poll \
	--listen-seconds 60
```

Or wait by name instead of fixed address:

```bash
python definition_protocol/example_ble_protocol_client.py \
	--name-contains laser \
	--wait-timeout 120 \
	--pair
```

## Data Privacy / Sanitization

This repository has been sanitized for public sharing:

- Real device MAC addresses were replaced with stable fake values in all `filtered_.log` files.
- Replacement map is documented in `test_on_android/devices.md`.
- Raw Bluetooth snoop files (`btsnoop_hci.log`) are git-ignored.
- Device inventory file (`test_on_android/devices.md`) is git-ignored.

Current sanitized mapping labels used in docs and notes:

- `phone_host`
- `gun_0`
- `gun_1`
- `gun_2`
- `gun_3`

## Limitations

- Some field meanings are inferred and may change with new captures.
- App/blaster firmware changes can shift payload families (for example `0x0a`-series to `0x0d`/`0x0e`-series).

## Next Steps

- Add stricter parser/tests for `protocol_definition.json`.
- Extend Python example to export decoded events as CSV/JSONL.
- Continue isolating upgrade-specific byte effects in controlled test runs.