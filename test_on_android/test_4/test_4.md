0: Delete app data
0: Connect only gun 0
0: Skip optional setup where possible
0: Enter single-player AR mode
0: set power-up: first shot after reload does more damage
0: Start game
0: count down beeps
0: Pause after connection/startup traffic stabilizes
0: Volume down sweep
0: Volume up sweep
0: Volume down sweep
0: cancel game from host
0: End test

## Notes

- Gun under test: g0
- Scenario: volume-only (no shooting, no gameplay)
- Sweep pattern: down, up, down
- Focus areas:
  - isolate volume-control payload family
  - map UI level to payload byte(s)
  - separate startup 5b1f from explicit volume changes

## Suggested timestamp log

- t_connect:
- t_startup_done:
- t_down_start:
- t_up_start:
- t_down2_start:
- t_end:

## Suggested per-step recording

- down: 10 9 8 7 6 5 4 3 2 1 0
- up: 0 1 2 3 4 5 6 7 8 9 10
- down2: 10 9 8 7 6 5 4 3 2 1 0

## Capture results

All `5bxx` writes on handle `0x0026` (host→gun):

| t (s) | payload | sweep |
|---|---|---|
| 34.4 | `5b1f` | startup default |
| 119.2 | `5b19` | down 1 |
| 120.1 | `5b15` | down 1 |
| 121.0 | `5b10` | down 1 |
| 121.8 | `5b0b` | down 1 |
| 122.6 | `5b07` | down 1 |
| 123.4 | `5b04` | down 1 |
| 125.2 | `5b00` | down 1 (min) |
| 126.2 | `5b02` | up |
| 127.0 | `5b03` | up |
| 127.9 | `5b06` | up |
| 129.5 | `5b0a` | up |
| 130.2 | `5b0f` | up |
| 131.1 | `5b14` | up |
| 131.9 | `5b18` | up |
| 132.7 | `5b1b` | up |
| 133.4 | `5b1f` | up (max) |
| 135.4 | `5b19` | down 2 |
| 136.2 | `5b15` | down 2 |
| 137.0 | `5b0f` | down 2 |
| 137.7 | `5b0b` | down 2 |
| 139.5 | `5b03` | down 2 |
| 140.2 | `5b00` | down 2 (min) |

### Conclusions

- `5bxx` = confirmed volume-set command
- Byte `xx` is a **continuous intensity value** 0x00–0x1f (0–31 decimal)
- `5b00` = mute/min, `5b1f` = max (also used as startup default)
- Intermediate values differ between sweeps → slider sends real-time position; no fixed discrete notches
- Volume controls only accessible during an active game session
