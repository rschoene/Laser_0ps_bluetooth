# Test 10: Different Default Stats Gun - Protocol Analysis

## Scope

This analysis is based on ATT traffic extracted from:
- [filtered_.log](filtered_.log)
- [test_10.md](test_10.md)

The capture contains two connect phases and one single-player game flow.

## High-Value New Findings

1. Startup snapshot format has a new fixed-byte template for this gun profile.

Observed startup reply (twice):
- `350012010200010a022704000a`

Compared to older captures (`35000a020201000aLLNNMM000a`), this changes bytes 2-7 from:
- old: `0a 02 02 01 00 0a`
- new: `12 01 02 00 01 0a`

What still holds:
- Byte 0 is still `35`
- Byte 8 still matches level (`02` here)
- Bytes 9-10 still behave like name-part fields (`27 04`)
- Byte 12 remains `0a`

Implication: assumptions that bytes 2/3/5/6/7 in startup are globally fixed across all guns are not valid. Those bytes are profile/firmware dependent.

2. Config writes also use the new template family.

Observed host writes:
- `360012010200010a022704000a`
- `360012010303010a0227040004`
- `360012020303010a0227040004`

This mirrors the startup template shift and confirms that the older `36` forms are not universal.

3. Reload marker B changed to `3112`.

Observed reload pairs:
- `52`
- followed by `3112` (three times)

This strongly supports that the second byte in `31xx` tracks magazine/reload-size state, now `0x12 = 18`, matching the test note that this gun starts with 18 ammo.

4. In-game control and ammo-state family shifted.

Observed in-game control:
- `37040100` (new value vs previously documented `370a0100` / `370e0100`)

Observed ammo notifications:
- dominant family: `3202xx`
- one additional frame: `320409`

This suggests the low-byte mode/capacity family can include `0x04` for this profile.

5. End-of-game stat exchange remains consistent with prior model.

Observed:
- host repeats `5a3f01010000` 10x
- gun replies `30013f0109` down to `30013f0100`
- terminal marker `3e0100`
- host closes with `42`

This validates that the end-of-game `5a3f`/`30013f`/`3e0100` flow is stable across this gun profile.

## Timeline Summary

- Connect #1 startup:
  - `35` -> `350012010200010a022704000a` -> `5b00`
- Reconnect startup:
  - same startup exchange
- App config/update phase:
  - `36...` / `57` / `36...`
- Game setup:
  - `4401`, `490100`, `36...`, `4a0000000000000000001388`, `411388`
- Gameplay:
  - multiple `49` trigger events
  - ammo counters via `3202xx`
  - reloads via `52` + `3112`
  - in-game control `37040100`
- End game:
  - repeated `5a3f01010000`
  - `30013f0109` -> ... -> `30013f0100`
  - `3e0100`, then `42`

## Assumption Validation

1. Level byte location (in startup/config) remains byte 8: validated.
- Startup shows level `0x02`, matching the note "level 2".

2. Name bytes remain in startup bytes 9-10: validated.
- `27 04` behaves exactly where earlier captures had name parts.

3. Startup bytes 2/3/5/6/7 are globally fixed constants: invalidated.
- Test 10 uses a different constant pattern.

4. Reload marker `31xx` second byte tracks ammo capacity/state: strengthened.
- `3112` aligns with 18-ammo default.

5. End-of-game stat protocol (`5a3f` <-> `30013f`, terminated by `3e0100`): validated.

## What This Adds To The Protocol Model

- There are at least two startup/config templates in the wild.
- Template-specific fixed bytes appear to vary by gun profile/firmware.
- The byte carrying level and the two name-part bytes remain stable by position.
- Reload-size family now includes `0x12` (18) in addition to older observed values (`0x0a`, `0x0d`).

## Suggested Next Verification Capture

To isolate meanings of the shifted fixed bytes, run a short controlled capture on this same gun:

1. Connect, no upgrades, no game start.
2. Change only volume.
3. Start game and fire exactly 1 full magazine with one reload.
4. End immediately.

This would separate startup/profile fields from gameplay-mode fields and tighten byte-level mapping around `3704` and `3204`.

## Cross-Test Check: Damage vs `5a3f` / `30013f`

This section compares single-player captures to answer whether end-stat packets encode per-hit damage or health synchronization.

### Evidence from Tests 2, 3, 6, 7, 10

- Test 3 note: start with 10 life, incoming damage described as always 1 until death.
  - End exchange: `5a3f01010000` repeated, replies `30013f0109` down to `30013f0100`.
- Test 10 note: level 2 gun with 18 ammo and about 10 health, incoming damage described as 1.
  - End exchange: `5a3f01010000` repeated, replies `30013f0109` down to `30013f0100`.
- Test 6 note: UI shows 15 life (health upgrade active).
  - End exchange: `5a3f01010000` repeated, replies `30013f010e` down to `30013f0100`.
- Test 7 note: level 5 profile with health upgrade still active.
  - End exchange includes class `TT=01` with top value `0e` and class `TT=06` (`30013f0608 ... 30013f0600`).
- Test 2 note: mixed incoming damage (1 or 2 depending on enemy).
  - End exchange alternates `TT=01` and `TT=02` requests; observed replies include `30013f0109`, `30013f0106`, `30013f0103`, `30013f0102` and `30013f0207`, `30013f0204`, `30013f0200`.

### Revised interpretation

The captures now fit a stronger model:

- in `5a3f010T0000`, byte `TT` is likely the damage value to apply
- in `30013fTTNN`, byte `NN` is likely the remaining HP after applying that damage

This is stronger than the earlier generic "stat class" interpretation because the mixed-damage sequences line up exactly with the handwritten notes.

### Why this fits well

1. Test 3 and Test 10: only 1-damage hits observed.
  - Host only sends `5a3f01010000`.
  - Replies walk down by 1 each time: `09 -> 08 -> ... -> 00`.
  - This matches 10 HP reduced by repeated 1-damage events.

2. Test 6: 15 life shown in UI.
  - Host only sends `5a3f01010000`.
  - Replies walk down by 1 from `0e` to `00`.
  - This matches 15 HP reduced by repeated 1-damage events.

3. Test 2: mixed 1- and 2-damage hits.
  - Ordered sequence is:
    - `5a3f01010000 -> 30013f0109`
    - `5a3f01020000 -> 30013f0207`
    - `5a3f01010000 -> 30013f0106`
    - `5a3f01020000 -> 30013f0204`
    - `5a3f01010000 -> 30013f0103`
    - `5a3f01010000 -> 30013f0102`
    - `5a3f01020000 -> 30013f0200`
  - Starting from 10 HP, this is exactly the remaining-HP sequence for incoming damage:
    - `10 - 1 = 9`
    - `9 - 2 = 7`
    - `7 - 1 = 6`
    - `6 - 2 = 4`
    - `4 - 1 = 3`
    - `3 - 1 = 2`
    - `2 - 2 = 0`

4. Test 7: `TT=06` also fits as a damage value.
  - One observed sequence is:
    - `5a3f01010000 -> 30013f010e`
    - `5a3f01060000 -> 30013f0608`
    - `5a3f01010000 -> 30013f0107`
    - `5a3f01060000 -> 30013f0601`
    - `5a3f01010000 -> 30013f0100`
  - Starting from 15 HP, this is exactly:
    - `15 - 1 = 14`
    - `14 - 6 = 8`
    - `8 - 1 = 7`
    - `7 - 6 = 1`
    - `1 - 1 = 0`

5. Overkill/clamping is supported.
  - Another Test 7 sequence includes `5a3f01060000 -> 30013f0600` while remaining HP before that step is only 4.
  - That fits a clamp-to-zero rule: if damage exceeds remaining HP, reply returns `00`.

### What follows from this

1. `TT` in `5a3f` is very likely a damage amount, not an abstract stat class.
  - Observed values so far: `01`, `02`, `06`.

2. `30013fTTNN` likely reports the new remaining HP after applying damage `TT`.

3. These messages are still not live health telemetry during gameplay.
  - They appear only in the end-of-game synchronization phase.
  - Best current interpretation: the app replays or finalizes outstanding damage against the gun so the gun-side health state reaches the same final value as the app-side session result.

4. This also explains why values above current HP can appear.
  - Damage larger than remaining HP is accepted and the returned HP is clamped to `00`.

### About Test 8 health

Test 8 is multiplayer and does not use the single-player `5a3f`/`30013f` flow.
It uses multiplayer end-round stats (`47` and `54`) and startup snapshots (`35...`) for persistent level/name state. Therefore Test 8 cannot be used to infer live single-player health from `30013f`.

## Cross-Test Check: Which Values Change In `5a3f`

Across all observed single-player tests, the request format is stable:

- `5a 3f 01 TT 00 00`

Observed payloads in captures:

- `5a3f01010000` in Tests 2, 3, 5, 6, 7, 10
- `5a3f01020000` in Test 2 only
- `5a3f01060000` in Test 7 only

### Byte-level conclusion

Only byte 3 (`TT`) changes across all observed `5a3f` requests, and the cross-test evidence now suggests this byte is the damage value being applied.

| Byte | Meaning | Observed values |
|---|---|---|
| 0 | fixed prefix | `5a` |
| 1 | fixed prefix | `3f` |
| 2 | fixed prefix | `01` |
| 3 | stat class selector `TT` | `01`, `02`, `06` |
| 4 | fixed zero | `00` |
| 5 | fixed zero | `00` |

### Per-test counts

| Test | Observed `5a3f` values |
|---|---|
| 2 | `5a3f01010000` ×5, `5a3f01020000` ×3 |
| 3 | `5a3f01010000` ×10 |
| 5 | `5a3f01010000` ×11 |
| 6 | `5a3f01010000` ×16 |
| 7 | `5a3f01010000` ×8, `5a3f01060000` ×4 |
| 10 | `5a3f01010000` ×10 |

So the currently supported model is now:

- `5a3f01` = fixed command family prefix
- `TT` = damage amount to apply during end-of-game health synchronization
- trailing `0000` = fixed padding / reserved bytes
