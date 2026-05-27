# LaserOps BLE Protocol — Observed Payload Reference

This page lists raw payload examples taken directly from Android BLE HCI captures.  Every example shown is a verbatim value seen in at least one capture session.

Confidence markers: **confirmed** = observed consistently; **inferred** = consistent but not proven; **medium/low** = tentative.

---

## Transport Summary

All payloads are flat byte sequences — there is no common framing header across message types.  Each message type is identified by its leading byte(s).

- **Host → gun**: ATT Write Command (`0x52`) to handle `0x0026`
- **Gun → host**: ATT Handle Value Notification (`0x1b`) from handle `0x0023`

Confirmed across all captures: Tests 1–9.

---

## Startup Exchange

### Host sends startup query

```
35
```

Length: 1 byte.  **Confidence: confirmed**.  Present in every test (Tests 1–9).

---

### Gun replies with startup snapshot

```
35 00 0a 02 02 01 00 0a  LL  NN  MM  00  0a
```

Length: 13 bytes.  **Confidence: confirmed structure; field names inferred**.

Observed in every test. The level byte `LL` at position 8 tracks the persistent gun level across sessions, but bytes 2–7 are now known to be template-dependent rather than globally fixed.

Observed examples (Test 1 — four guns):

```
35 00 0a 02 02 01 00 0a  03  17  32  00  0a   ← gun 0, level 3
35 00 0a 02 02 01 00 0a  02  0f  0f  00  0a   ← gun 1, level 2
35 00 0a 02 02 01 00 0a  00  00  00  00  0a   ← gun 2, unnamed
35 00 0a 02 02 01 00 0a  02  32  31  00  0a   ← gun 3, level 2
```

Test 6 (gun 0 after reaching level 4, same fixed bytes 2 and 7 despite level change — confirms they do not encode live health/ammo):

```
35 00 0a 02 02 01 00 0a  04  12  14  00  0a
```

Test 9 (blaster A level 2, blaster B level 5 — multiplayer startup snapshots identical in structure):

```
35 00 0a 02 02 01 00 0a  02  02  04  00  0a   ← blaster A
35 00 0a 02 02 01 00 0a  05  12  14  00  0a   ← blaster B
```

Test 10 (alternate profile template, same `LL NN MM` positions):

```
35 00 12 01 02 00 01 0a  02  27  04  00  0a
```

---

### Host sends initial volume

```
5b  XX
```

Length: 2 bytes. `XX` = `1f` (31, max) when app persists max volume; `00` when muted.  Follows immediately after the startup snapshot in every test.

- Tests 1–5, 7–9: `5b 1f` (persisted max)
- Test 6: `5b 00` (persisted muted volume)
- Test 9 (multiplayer): `5b 00` sent per blaster during round setup

---

## Config Write (Single-Player Mode, Tests 1–7, 10, 14, 16)

Config writes are observed only in single-player mode.  They are absent from the multiplayer captures (Tests 8–9).

### Host writes level + name config to gun

```
36 00 0a 02 02 01 00 0a  LL  NN  MM  00  0a   ← form A
36 00 0a 02 02 03 00 0a  LL  NN  MM  00  04   ← form B
36 00 0d 03 02 03 00 0f  LL  NN  MM  00  VV   ← form C (level 4+)
36 03 AA DD 02 03 00 HH  LL  NN  MM  00  RR   ← form E (Test 16 high-level family)
```

Length: 13 bytes.  **Confidence: confirmed structure; `LL` field high confidence**.

Observed examples from Test 1 (after app assigned names):

```
36 00 0a 02 02 03 00 0a  03  12  14  00  04   ← gun 0, level 3, name idx 17+1/19+1
36 00 0a 02 02 03 00 0a  02  02  04  00  04   ← gun 1, level 2, name idx 1+1/3+1
36 00 0a 02 02 03 00 0a  01  03  05  00  04   ← gun 2, level 1, name idx 2+1/4+1
36 00 0a 02 02 03 00 0a  02  04  0a  00  04   ← gun 3, level 2
```

Test 6 baseline write (level 4) and comparison with level-3 write (Test 1 gun 0):

```
36 00 0d 03 02 03 00 0f  04  12  14  00  04   ← Test 6, level 4
36 00 0a 02 02 03 00 0a  03  12  14  00  04   ← Test 1 gun 0, level 3
```

Changed byte positions when level moved 3→4 (Tests 1→6): bytes 2 (`0a`→`0d`), 3 (`02`→`03`), 7 (`0a`→`0f`), 8 (`03`→`04`).

Test 7 — level-5 writes (same gun, later phase of capture):

```
36 00 0a 02 02 01 00 0a  05  12  14  00  0a
36 00 0a 02 02 03 00 0a  05  12  14  00  04
36 00 0d 03 02 03 00 0f  05  12  14  00  03
```

Confirmed rule for the trailing byte (`VV`) in the standard single-player template family (`...020203000a...`):

- `VV = 03` when only reactivation-time is selected (no reload-speed).
- `VV = 04` when only reload-speed is selected (no reactivation-time).

Test 14 confirms this directly with isolated runs on the same gun:
- runs 1-2 (reload-only): `36000a020203000a0512140004`
- runs 3-4 (reactivation-only): `36000a020203000a0512140003`

Tests 6/7 remain consistent with this mapping in the level-4+/form-C family.

Test 10 — alternate profile template family:

```
36 00 12 01 02 00 01 0a  02  27  04  00  0a
36 00 12 01 03 03 01 0a  02  27  04  00  04
36 00 12 02 03 03 01 0a  02  27  04  00  04
```

These values preserve the same level/name positions (`LL NN MM`) while changing the preceding framing bytes.

Test 16 — high-level gun 2 profile family:

```
36 03 0a 02 02 03 00 0a  0c  03  05  00  04   ← baseline: ammo 10, damage 2, health 10, react 10 s
36 03 0a 02 02 03 00 0f  0c  03  05  00  04   ← health 15
36 03 0a 02 02 03 00 14  0c  03  05  00  04   ← health 20
36 03 0d 02 02 03 00 0a  0c  03  05  00  04   ← ammo 13
36 03 10 02 02 03 00 0a  0c  03  05  00  04   ← ammo 16
36 03 0a 03 02 03 00 0a  0c  03  05  00  04   ← damage 3
36 03 0a 04 02 03 00 0a  0c  03  05  00  04   ← damage 4
36 03 0a 02 02 03 00 0a  0c  03  05  00  03   ← react 9 s
36 03 0a 02 02 03 00 0a  0c  03  05  00  02   ← react 8 s
```

Candidate correlation for form E only:

- `AA` varies with ammo-capacity UI state: `0a` → `0d` → `10` for ammo `10` → `13` → `16`.
- `DD` varies with damage UI state: `02` → `03` → `04` for damage `2` → `3` → `4`.
- `HH` varies with health UI state: `0a` → `0f` → `14` for health `10` → `15` → `20`.
- `RR` varies with reactivation UI state: `04` → `03` → `02` for reactivation `10 s` → `9 s` → `8 s`.
- `LL` remains `0c` (level 12), and `NN MM` remain `03 05` (`Atom Beast`) across the run set.

This Test 16 mapping is still candidate-level correlation, not a fully confirmed universal field decode. The two reload-time attempts in Test 16 produced no visible UI change and no `36...` delta, so they do not yet establish a reload-time byte mapping.

---

### Host sends apply/commit

```
57
```

Length: 1 byte.  Sent after config writes.  **Confidence: confirmed placement; inferred meaning**.  Present in Tests 1–7; not observed in multiplayer captures (Tests 8–9).

---

## Volume Control

```
5b  XX
```

`XX` range: `00` (mute) to `1f` (max = 31 decimal).  Continuous slider position — not discrete steps.  **Confirmed: Tests 4 and 6**.

Test 4 sweep data (three sweeps, game session active, no shooting):

| Time (s) | Payload  | Phase          |
|----------|----------|----------------|
| 34.4     | `5b 1f`  | startup default |
| 119.2    | `5b 19`  | down sweep 1   |
| 120.1    | `5b 15`  | down sweep 1   |
| 121.0    | `5b 10`  | down sweep 1   |
| 121.8    | `5b 0b`  | down sweep 1   |
| 122.6    | `5b 07`  | down sweep 1   |
| 123.4    | `5b 04`  | down sweep 1   |
| 125.2    | `5b 00`  | down sweep 1 (min) |
| 126.2    | `5b 02`  | up sweep       |
| 127.0    | `5b 03`  | up sweep       |
| 127.9    | `5b 06`  | up sweep       |
| 129.5    | `5b 0a`  | up sweep       |
| 130.2    | `5b 0f`  | up sweep       |
| 131.1    | `5b 14`  | up sweep       |
| 131.9    | `5b 18`  | up sweep       |
| 132.7    | `5b 1b`  | up sweep       |
| 133.4    | `5b 1f`  | up sweep (max) |

Test 3: `5b 19 5b 11 5b 09 5b 02 5b 00` observed during a volume-down phase.

Test 6: startup volume is `5b 00` (muted) because the app had persisted that state.

---

## Periodic Status

### Poll (host → gun, every ~27 s)

```
51
```

### Reply (gun → host)

```
51  XX  YY
```

Observed values (3 bytes, status word drifts upward over time):

```
51 03 32   51 03 33   51 03 34   51 03 35   ← gun 0 (Test 1)
51 02 bf   51 02 c2   51 02 c3              ← gun 1 (Test 1)
51 03 3e   51 03 3f   51 03 40              ← gun 2 (Test 1)
51 02 b9   51 02 bb                         ← gun 3 (Test 1)
```

`51` exchanges are present in Tests 1, 6, 7, and 8.  **Notably absent from the extracted Test 9 command/notification stream**, confirming that `51` is not required for the multiplayer round-control flow.  Best current interpretation: likely battery or keepalive status, not gameplay polling.  **Confidence: inferred**.

---

## Single-Player Gameplay Events (Tests 1–7)

These messages are observed in single-player AR mode only.  They are absent from the multiplayer captures (Tests 8–9).

### Trigger / fire (gun → host)

```
49
```

Single byte, one per trigger pull.  **Confidence: high**.  Confirmed in Tests 1–7.

- Test 1: gun 0 = 3 events, gun 1 = 4, gun 2 = 0, gun 3 = 10
- Test 2: 41 events (active gameplay round)
- Test 3: 10 events (shoot-only, no reload)

### Reload marker pair (gun → host)

First byte, then ~0.5 s later second byte:

```
52          ← reload marker A
31 0a       ← reload marker B (older mode, Tests 2–6, levels 1–4)
31 0d       ← reload marker B (newer mode, Test 7, level 5)
31 12       ← reload marker B (alternate profile, Test 10, 18 ammo)
```

Tests 2, 5, 6: `52` + `310a` pairs observed (reload confirmed by test notes).
Test 3: no `52` or `310a` observed — test was shoot-only, no manual reload.  This negative result strengthens the reload interpretation.
Test 7: `52` + `310d` pairs observed.  The shift from `0a` (10) to `0d` (13) is consistent with a Munition upgrade increasing the magazine size.
Test 10: `52` + `3112` pairs observed.  The `0x12 = 18` value matches the handwritten note that this gun starts with 18 ammo.  **Confidence: inferred-high**.

### Ammo / shot state (gun → host)

Older mode (Tests 2–6):

```
32 02 XX    (e.g. 32 02 09, 32 02 08, 32 02 07 …)
32 0a XX
```

Newer mode (Test 7):

```
32 03 XX
32 0e XX
```

Alternate profile (Test 10):

```
32 02 XX
32 04 XX    (observed as `320409`)
```

`XX` appears to be a descending counter.  **Confidence: medium-high**.

---

### In-game control (host → gun)

```
37 0a 01 00   ← older mode (Tests 2–6, 6 times in Test 2)
37 0e 01 00   ← newer mode (Test 7)
37 04 01 00   ← alternate profile (Test 10)
```

Candidate meaning: reload / special-shot state transition.  **Confidence: medium**.

---

### Single-player setup commands (Tests 2–7, low confidence)

Observed in Test 2 only, immediately before gameplay:

```
44 01
41 13 88
3b 07
39 0a
```

Candidate meanings: game-mode init flag (`44`), countdown/scoring parameter (`41`, `3b`, `39`).  **Confidence: low**.

---

## End-of-Game Statistics (Single-Player Mode, Tests 2–7)

These stat messages are observed only in single-player mode.  They are absent from the multiplayer captures (Tests 8–9), which use `47` and `54` instead.

### Stat request (host → gun, repeated with different TT values)

```
5a 3f 01  TT  00 00
```

Observed `TT` values: `01`, `02`, `06`.  Present in Tests 2, 3, 5, 6, 7, 10.  Best current interpretation: `TT` is the damage amount being applied during the end-of-game health synchronization. **Confidence: high**.

### Stat counter reply (gun → host)

```
30 01 3f  TT  NN
```

Best current interpretation:

- `TT` echoes the damage amount from the `5a3f...` request
- `NN` is the remaining HP after applying that damage

Representative sequences:

- Test 3 / Test 10: `30013f0109` down to `30013f0100` for repeated 1-damage sync on a 10-HP gun
- Test 6: `30013f010e` down to `30013f0100` for repeated 1-damage sync on a 15-HP gun
- Test 2: mixed `TT=01` / `TT=02` gives `09 -> 07 -> 06 -> 04 -> 03 -> 02 -> 00`
- Test 7: mixed `TT=01` / `TT=06` gives `0e -> 08 -> 07 -> 01 -> 00`

Damage larger than remaining HP is clamped to `00`.

### End-of-game terminal marker (gun → host)

```
3e 01 00
```

**Confidence: medium**.  Present in Tests 2–7.

---

## Session Close

```
42
```

Single byte, sent by host to terminate the session.  **Confidence: confirmed**.

In single-player mode (Tests 1–7): appears once at the very end of the session.
In multiplayer mode (Tests 8–9): appears as part of the interleaved end-of-round exchange alongside `47` shot-count notifications and `54` stat queries.  Tests 8 and 9 both show `47`, `42`, and `54` interleaved during the round-close phase — `42` does not occur strictly after all `47` events.

---

## Multiplayer Mode (Tests 8–9)

These messages are present only in multiplayer captures.  The single-player gameplay events (`49` trigger, `52`/`31`, `32`, `37`) are absent from Tests 8 and 9.

The full per-blaster setup order per round is:

1. `49 SS TT` — host assigns slot/team to this blaster
2. `4a ... DD DD ...` — host sends round configuration (includes duration)
3. `5b 00` — host sets volume
4. `35` — host sends startup query
5. `35 ...` — gun replies with startup snapshot
6. `58` — host arms/starts the round for this blaster

Round close (interleaved, order varies per blaster):

- `47 HI LO` — blaster reports aggregate shot count for the completed round
- `42` — host sends session-close command to this blaster
- `54 SS` — host queries per-slot stats
- `54 00 ... SS` — gun replies with per-slot hit/kill stats

### `49 SS TT` — multiplayer assignment (host → gun)

```
49 SS TT
```

`SS` = slot index; `TT` = team indicator.  Sent once per blaster before each round.  **Confidence: high — Tests 8 and 9 both show host-originated direction and consistent slot/team patterns**.

Test 9 examples:
- Round 1: `49 02 00` (blaster A, slot 2, team 0), `49 03 01` (blaster B, slot 3, team 1)
- Round 2: `49 04 00` (blaster A, slot 4, team 0), `49 05 01` (blaster B, slot 5, team 1)

Note: in earlier single-player captures (Tests 2–7), the single-byte gun→host notification `49` was interpreted as a trigger/fire event.  That single-byte form and this 3-byte host→gun form are distinguished by both direction and length.

### `4a` — round configuration (host → gun)

```
4a 00 0a ff  DD DD  00 00 00 00  27 10
```

`DD DD` = round duration in seconds (big-endian 16-bit).  **Confidence: very strong — duration bytes match documented round lengths exactly in both Tests 8 and 9**.

Test 9 (3-minute rounds): `4a 00 0a ff 00 b4 00 00 00 00 27 10`  — `0x00b4 = 180 s`

Test 8 observed two distinct values:
- Round 1: `4a 00 0a ff 00 b4 00 00 00 00 27 10` — `0x00b4 = 180 s`  (3 min)
- Round 2: `4a 00 0a ff 01 2c 00 00 00 00 27 10` — `0x012c = 300 s`  (5 min)

### `58` — round arm / start (host → gun)

```
58
```

Single byte.  Sent once per connected blaster after the per-blaster setup sequence, immediately before the round begins.  **Confidence: strong — Tests 8 and 9 both show `58` as the final pre-round host command per blaster**.

### `47 HI LO` — end-of-round shot count (gun → host)

```
47  HI  LO
```

16-bit big-endian shot count for the completed round.  Reported once per blaster during the round-close exchange.  **Confidence: very strong — byte values match handwritten shot counts exactly in Test 9**.

Test 9 exact matches:
- Round 1: `47 00 1e` — `0x001e = 30` shots (note: "shoots 30 times")
- Round 1: `47 00 00` — `0x0000 = 0` (opposing blaster, no shots)
- Round 2: `47 00 0a` — `0x000a = 10` shots (note: "shoots 10 times")
- Round 2: `47 00 00` — `0x0000 = 0` (opposing blaster)

Test 8 values (four blasters, two rounds — harder to match individually due to IR crosstalk):
- Round 1: `47 00 08`, `47 00 0f`, `47 00 00`, `47 00 00`
- Round 2: `47 00 0d`, `47 00 14`, `47 00 00`, `47 00 00`

### `54` — per-slot stat query and reply (host ↔ gun)

Host query (host → gun):

```
54  SS
```

Gun reply (gun → host):

```
54 00  HH  KK  SS
```

`SS` = queried slot index (echoed in reply); `HH` = hits received; `KK` = kills.  **Confidence: very strong — values match handwritten hit/kill totals exactly in Test 9**.

Test 9 exact matches (Round 1):
- Host: `54 02`, reply: `54 00 00 00 02` → slot 2, 0 hits, 0 kills (blaster A in losing role)
- Host: `54 03`, reply: `54 00 0a 02 03` → slot 3, 10 hits, 2 kills — matches note "hits 10 times, kills 2 times"

Test 9 exact matches (Round 2):
- Host: `54 04`, reply: `54 00 00 00 04` → slot 4, 0 hits, 0 kills
- Host: `54 05`, reply: `54 00 07 01 05` → slot 5, 7 hits, 1 kill — matches note "hits 7 times, kills 1 times"

Test 8 shows the same query/reply pattern across four blasters and two rounds, but individual attribution is harder due to overlapping IR hits.

---

## Level-5 State Writes (Test 7)

New `36` writes with level byte `05` appeared in the later phase of Test 7, after the gun levelled up during capture.  The form-C prefix (`0d 03 ... 0f`) also appeared at level 4 (Test 6):

```
36 00 0a 02 02 01 00 0a  05  12  14  00  0a
36 00 0a 02 02 03 00 0a  05  12  14  00  04
36 00 0d 03 02 03 00 0f  05  12  14  00  03
```

---

## Sources

- [test_on_android/test_1/traffic_definition.md](../test_on_android/test_1/traffic_definition.md) — Tests 1–7 detailed analysis
- [test_on_android/test_1/test_1.md](../test_on_android/test_1/test_1.md) — four-gun baseline session
- [test_on_android/test_2/test_2.md](../test_on_android/test_2/test_2.md) — single-player AR, trigger/reload/stats
- [test_on_android/test_3/test_3.md](../test_on_android/test_3/test_3.md) — single-player, shoot-only (reload absence)
- [test_on_android/test_4/test_4.md](../test_on_android/test_4/test_4.md) — volume sweep
- [test_on_android/test_5/test_5.md](../test_on_android/test_5/test_5.md) — level-up capture
- [test_on_android/test_6/test_6.md](../test_on_android/test_6/test_6.md) — level-4 state delta
- [test_on_android/test_7/test_7.md](../test_on_android/test_7/test_7.md) — level-5 transition
- [test_on_android/test_8/analysis.md](../test_on_android/test_8/analysis.md) — four-blaster multiplayer team battle
- [test_on_android/test_9/analysis.md](../test_on_android/test_9/analysis.md) — two-blaster multiplayer, exact stat match
- [definition_protocol/protocol_definition.json](../definition_protocol/protocol_definition.json)

