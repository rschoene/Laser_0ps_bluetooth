# Protocol Definition For Python

This folder contains a machine-readable protocol definition and a runnable Python BLE example.

## Files

- `protocol_definition.json`: reverse-engineered protocol model
- `example_ble_protocol_client.py`: scanner + pairing + connect + notify + debug prints

## Install

```bash
pip install bleak
```

## Example usage

Wait for a specific address, pair, send startup writes, and print decoded notifications:

```bash
python definition_protocol/example_ble_protocol_client.py \
  --address <gun_0_address> \
  --pair \
  --send-startup \
  --startup-volume 0 \
  --send-poll \
  --listen-seconds 60
```

Wait by name match instead of fixed MAC (useful before pairing or with randomized addresses):

```bash
python definition_protocol/example_ble_protocol_client.py \
  --name-contains laser \
  --wait-timeout 120 \
  --pair \
  --listen-seconds 30
```

## Notes

- Handles default to protocol values:
  - notify: `0x0023`
  - write: `0x0026`
- Pairing support depends on OS/backend support in Bleak.
- The protocol file includes inferred fields; treat semantics tagged as inferred as tentative.
- `protocol_definition.json` intentionally contains no hardcoded device MAC addresses.
