# Laser_0ps_bluetooth

Reverse-engineering and Python/web tooling for **Hasbro NERF LaserOps** over Bluetooth Low Energy (BLE).

The main goal is safe and repeatable multi-blaster operation through a local server
(typically a Raspberry Pi as the central host).

## Contributing

Contributions (additional HCI captures, corrections, clarifications) are welcome, especially for Hasbro Nerf LaserOps Pro DeltaBurst devices, of which I only have one. Please open an issue or a pull request. If you provide an HCI capture, it would be great if you'd document what you did (number of devices, game mode and setup, estimation or detailed description of statistics and so on). Check test_on_android/test_definition.md on how to capture HCI protocols on Android.

## Credits

- `rschoene`
- `PatrickKalka-SeriousByte`

## Project Goals

- Document and validate the BLE protocol¹ in practical usage
- Manage multiple blasters from a browser UI
- Start and control rounds with explicit slot/team assignment
- Run reliably as a long-lived local service (Raspberry Pi target)
- Long term: have an ESP with a display host the game 😉

¹ All protocol knowledge comes from BLE HCI snoop captures of the official Hasbro Android app (see test_on_android/ for raw logs and analysis).
**Note**: Confidence levels for protocol fields vary.

## Repository Layout

```text
Laser_0ps_bluetooth/
  README.md
  scripts/                 # BLE core and CLI tooling
  webapp/                  # FastAPI backend + web UI
  protocol/                # Human-readable protocol documentation
  definition_protocol/     # Machine-readable protocol definition
  test_on_android/         # Capture notes and reverse-engineering evidence
```

## Web UI Quick Start

Please have a look at `webapp/QUICKSTART.md`

## Safety Notice (BLE Reverse Engineering)

All BLE command semantics are based on reverse engineering, not official vendor protocol documentation.
Safety guards are implemented (command allow-list, strict bounds, write throttling), but absolute guarantees
for every firmware behavior are technically not possible.

## Documentation

- Web app details: `webapp/README.md`
- Protocol details: `protocol/README.md` and `protocol/packets.md`
- Android capture workflow: `test_on_android/test_definition.md`

## License

GNU General Public License v3.0, see [LICENSE](LICENSE).
