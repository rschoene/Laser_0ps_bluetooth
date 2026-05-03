# LaserOps BLE Protocol — Observed Payload Reference

This page lists raw payload examples taken directly from Android BLE HCI captures.  Every example shown is a verbatim value seen in at least one capture session.

Confidence markers: **confirmed** = observed consistently; **inferred** = consistent but not proven; **medium/low** = tentative.

---

## Transport Summary

All payloads are flat byte sequences — there is no common framing header across message types.  Each message type is identified by its leading byte(s).

- **Host → gun**: ATT Write Command (`0x52`) to handle `0x0026`
- **Gun → host**: ATT Handle Value Notification (`0x1b`) from handle `0x0023`

---

## Startup Exchange

### Host sends startup query

```
35
```

Length: 1 byte.  **Confidence: confirmed**.

---

### Gun replies with startup snapshot

```
35 00 0a 02 02 01 00 0a  LL  NN  MM  00  0a
```

Length: 13 bytes.  **Confidence: confirmed structure; field names inferred**.

Observed examples (Test 1 — four guns):

```
35 00 0a 02 02 01 00 0a  03  17  32  00  0a   ← gun 0, level 3
35 00 0a 02 02 01 00 0a  02  0f  0f  00  0a   ← gun 1, level 2
35 00 0a 02 02 01 00 0a  00  00  00  00  0a   ← gun 2, unnamed
35 00 0a 02 02 01 00 0a  02  32  31  00  0a   ← gun 3, level 2
```

Test 6 (gun 0 after reaching level 4):

```
35 00 0a 02 02 01 00 0a  04  12  14  00  0a
```

---

### Host sends initial volume

```
5b  XX
```

Length: 2 bytes. `XX` = `1f` (31, max) when app persists max volume; `00` when muted (observed in Test 6).

---

## Config Write

### Host writes level + name config to gun

```
36 00 0a 02 02 01 00 0a  LL  NN  MM  00  0a   ← form A
36 00 0a 02 02 03 00 0a  LL  NN  MM  00  04   ← form B
36 00 0d 03 02 03 00 0f  LL  NN  MM  00  VV   ← form C (level 4+)
```

Length: 13 bytes.  **Confidence: confirmed structure; `LL` field high confidence**.

Observed examples from Test 1 (after app assigned names):

```
36 00 0a 02 02 03 00 0a  03  12  14  00  04   ← gun 0, level 3, name idx 17+1/19+1
36 00 0a 02 02 03 00 0a  02  02  04  00  04   ← gun 1, level 2, name idx 1+1/3+1
36 00 0a 02 02 03 00 0a  01  03  05  00  04   ← gun 2, level 1, name idx 2+1/4+1
36 00 0a 02 02 03 00 0a  02  04  0a  00  04   ← gun 3, level 2
```

Test 6 baseline write (level 4):

```
36 00 0d 03 02 03 00 0f  04  12  14  00  04
```

Previous level-3 baseline write for comparison:

```
36 00 0a 02 02 03 00 0a  03  12  14  00  04
```

Changed byte positions when level moved 3→4: bytes 2 (`0a`→`0d`), 3 (`02`→`03`), 7 (`0a`→`0f`), 8 (`03`→`04`).

---

### Host sends apply/commit

```
57
```

Length: 1 byte.  Sent after config writes.  **Confidence: confirmed placement; inferred meaning**.

---

## Volume Control

```
5b  XX
```

`XX` range: `00` (mute) to `1f` (max = 31 decimal).  Continuous slider position — not discrete steps.

Test 4 sweep data (three sweeps, no gameplay):

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
51 03 32   51 03 33   51 03 34   51 03 35   ← gun 0
51 02 bf   51 02 c2   51 02 c3              ← gun 1
51 03 3e   51 03 3f   51 03 40              ← gun 2
51 02 b9   51 02 bb                         ← gun 3
```

---

## Gameplay Events

### Trigger / fire (gun → host)

```
49
```

Single byte, one per trigger pull.  **Confidence: high**.

### Reload marker pair (gun → host)

First byte, then ~0.5 s later second byte:

```
52          ← reload marker A
31 0a       ← reload marker B (older mode, Tests 1–6)
31 0d       ← reload marker B (newer mode, Test 7)
```

The second byte in the reload marker B (`0a` / `0d`) may represent the number of ammunition reloaded per cycle — `0x0a` = 10 in older mode (Tests 1–6, levels 1–4) and `0x0d` = 13 in newer mode (Test 7, level 5).  This is consistent with a Munition upgrade increasing the magazine size.  **Confidence: inferred**.

### Ammo / shot state (gun → host)

Older mode (Tests 1–6):

```
32 02 XX    (e.g. 32 02 09, 32 02 08, 32 02 07 …)
32 0a XX
```

Newer mode (Test 7):

```
32 03 XX
32 0e XX
```

`XX` appears to be a descending counter.  **Confidence: medium-high**.

---

## In-Game Control

```
37 0a 01 00   ← older mode (Tests 2–6, 6 times in Test 2)
37 0e 01 00   ← newer mode (Test 7)
```

Candidate meaning: reload / special-shot state transition.  **Confidence: medium**.

---

## Game Setup (observed in Test 2 — semantics low confidence)

```
44 01
49 01 00
4a 00 00 00 00 00 00 00 00 00 13 88
41 13 88
3b 07
39 0a
```

---

## End-of-Game Statistics

### Stat request (host → gun, repeated with different TT values)

```
5a 3f 01  TT  00 00
```

Observed `TT` values: `01`, `02`, `06`.  **Confidence: inferred**.

### Stat counter reply (gun → host)

```
30 01 3f  TT  NN
```

`NN` descends from an upper bound down to `00`.  Upper bound observed per level:
- Level 3 (Tests 2–3): upper bound `09`
- Level 4 (Test 6):    upper bound `0e`
- Level 5 (Test 7):    values `00 04 05 06 07 0e` (multi-round capture)

### End-of-game terminal marker (gun → host)

```
3e 01 00
```

**Confidence: medium**.

---

## Session Close

```
42
```

Single byte, last host command.  **Confidence: low-medium**.

---

## Level-5 State Writes (Test 7)

New `36` writes with level byte `05` appeared in the later phase of Test 7:

```
36 00 0a 02 02 01 00 0a  05  12  14  00  0a
36 00 0a 02 02 03 00 0a  05  12  14  00  04
36 00 0d 03 02 03 00 0f  05  12  14  00  03
```

---

## Sources

- `test_on_android/test_1/traffic_definition.md`
- `test_on_android/test_2/test_2.md` through `test_7/test_7.md`
- `definition_protocol/protocol_definition.json`

