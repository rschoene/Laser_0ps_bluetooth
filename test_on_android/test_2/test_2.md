0: Delete app data
0: Connect only gun 0
0: Skip optional setup where possible
0: some points unused - no power ps or upgrades
0: Enter single-player AR mode
0: set power-up: first shot after reload does more damage
0: Start game with 10 life points
0: count down, inluding periodic sounds on gun
0: Track enemies with smartphone camera
0: Test trigger
0: Test trigger
0: Test trigger
0: (triggers and reloads), most often hitting enemies, collect power ups (less then 5 times)
0: stop shooting and die by getting damage (1/2 damage depending on enemy)
0: receive 27 xp in the end
0: End test

## Notes

- Gun under test: g0
- Goal: isolate single-player AR traffic
- Focus areas:
  - trigger event traffic
  - reload-related traffic
  - sound-related traffic
  - level/progression-related traffic
- Compare against test_1 traffic to identify new message patterns

## Capture Results (from filtered_.log)

### Connection and startup

1. Only one gun conversation is present: `phone_host` <-> `gun_0`.
2. Startup sequence is present and matches Test 1 baseline:
   - host `35` on handle `0x0026`
   - gun `35 00 0a 02 02 01 00 0a 03 12 14 00 0a` on handle `0x0023`
   - host `5b1f` on handle `0x0026`
3. No "unknown gun" startup snapshot was found in this capture.
4. Specifically, the zeroed startup payload `35 00 0a 02 02 01 00 0a 00 00 00 00 0a` did not occur.

Interpretation:
- Even after deleting app data, gun 0 appears to present known/non-zero identity bytes (`03 12 14`) in startup.
- This suggests the gun retained identity/config state, or that this state is sourced from the gun side.

### Trigger traffic

1. Trigger event `49` on handle `0x0023` is present 41 times.
2. During active shooting, each `49` is frequently followed by a `32....` notification (for example `320209`, `320208`, `320207`).

Interpretation:
- `49` still maps to trigger/fire event with high confidence.
- `32....` likely carries per-shot or ammo/state update information.

### New gameplay-specific traffic (not seen in Test 1 baseline)

Host -> gun, handle `0x0026`:
1. `370a0100` (6 times)
2. `4401` (1 time)
3. `490100` (1 time)
4. `4a0000000000000000001388` (1 time)
5. `411388` (1 time)
6. `3b07` (1 time)
7. `390a` (1 time)
8. `5a3f01010000` (5 times)
9. `5a3f01020000` (3 times)
10. `42` (1 time)

Gun -> host, handle `0x0023`:
1. `52` (4 times), each followed about 0.5 s later by `310a` (4 times)
2. `3202xx` and `320axx` families (multiple values)
3. `30013f....` family near end of session
4. `3e0100` once near end of session

Interpretation:
- The `52 -> 310a` pair is a strong candidate for reload/sound lifecycle signaling.
- The `3202xx`/`320axx` families are likely in-game counters or ammo/shot state changes.
- The `30013f....` and `3e0100` near the end likely correspond to end-of-round summary or XP/progression events.

### Level/progression signal

1. Startup/config still uses `... 03 12 14 ...` for gun 0 (same tuple as before).
2. No clear in-session change of the level byte in the `36...` config format was observed in this capture.
3. End-of-session new message families (`30013f....`, `3e0100`) are the best candidates for XP/progression reporting.

### Conclusion for Test 2 objective

1. Single-player AR gameplay traffic is clearly present and richer than Test 1.
2. Trigger event traffic is strongly confirmed (`49`, 41 occurrences).
3. Reload/sound related traffic is likely present (`52` + `310a` paired notifications and additional host commands like `370a0100`).
4. Unknown-gun initialization was not observed in this specific capture.
