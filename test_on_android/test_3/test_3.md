0: Delete app data
0: Connect only gun 0
0: Skip optional setup where possible
0: Enter single-player AR mode
0: set power-up: first shot after reload does more damage
0: Start game
0: Shoot only (no manual reload)
0: Track enemies with smartphone camera
0: Test trigger
0: Test trigger
0: Test trigger
0: Continue shooting
0: 7 hits on enemies, 2 hits on power-ups, 1 miss, total 10 shots
0: pause
0: reduce volume in multiple steps
0: unpause
0: get shot, always 1 damage until dead (10 LP on start)
0: End game/session
0: get 7 xp to a total of 328
0: End test

## Notes

- Gun under test: g0
- Scenario: single-player AR, no reload
- Additional phase: volume sweep 10 -> 0
- Focus areas:
  - trigger event traffic
  - absence/reduction of reload-like traffic compared with test_2
  - payload changes per volume step
  - sound-related message patterns

## Capture Results (from filtered_.log)

### Session and startup

1. Single conversation only: `phone_host` <-> `gun_0`.
2. Standard startup sequence is present:
  - host `35` on handle `0x0026`
  - gun `35 00 0a 02 02 01 00 0a 03 12 14 00 0a` on handle `0x0023`
  - host `5b1f` on handle `0x0026`

### Trigger and no-reload check

1. Trigger event `49` appears 10 times.
2. Reload-like pair from Test 2 (`52` followed by `310a` on gun notifications) is absent.
3. This supports the no-reload scenario behavior in this run.

### Volume-step traffic candidates

During the pause/reduce-volume phase, host sends these `5bxx` commands:

- `5b19` at 147.078 s
- `5b11` at 147.974 s
- `5b09` at 148.844 s
- `5b02` at 149.768 s
- `5b00` at 150.803 s

Interpretation:

- `5bxx` is a strong candidate family for volume setting.
- The second byte likely carries the target volume value or an encoded attenuation step.
- Captured values are descending and consistent with lowering volume toward minimum.

### Other gameplay and end-of-round traffic

1. Trigger-adjacent notifications still include `3202xx` and `320axx` values.
2. End-of-session/stat traffic appears as:
  - host repeated `5a3f01010000`
  - gun responses `30013f0109` down to `30013f0100`
  - terminal marker `3e0100`
  - host close/ack `42`

### Conclusion

1. Test 3 successfully isolates shooting without reload.
2. Volume changes produce distinct host command payloads (`5bxx`).
3. Best next step: run a short volume-only test (no gameplay) with explicit per-step timestamps to map each UI level (10..0) to exact `xx` byte values.
