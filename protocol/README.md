# LaserOps BLE Protocol — Transport and Message Reference

All information on this page is derived from Android BLE HCI captures of the official Hasbro app (see `test_on_android/`).

Confidence markers used throughout:
- **Confirmed** — observed consistently across multiple independent captures.
- **High** — strongly supported by capture evidence.
- **Inferred** — consistent with observed traffic, but exact semantics not yet proven.
- **Low / Medium** — limited observations; treat as tentative.

---

## Transport Layer

Communication uses the ATT (Attribute Protocol) layer directly.  No custom GATT service UUIDs have been identified from captures; all known traffic uses two fixed ATT handles.

| Direction     | ATT opcode | ATT opcode name        | Handle   |
|---------------|------------|------------------------|----------|
| Host → gun    | `0x52`     | Write Command          | `0x0026` |
| Gun → host    | `0x1b`     | Handle Value Notification | `0x0023` |
| Setup (once)  | `0x12`     | Write Request          | `0x0024` |

The Write Request on handle `0x0024` is sent once at connection setup (presumably to enable notifications).  All subsequent host→gun traffic uses Write Command (`0x52`) on `0x0026`.

---

## Startup Sequence

Observed order for every connected gun (confirmed across all tests):

| Step | Direction     | Handle   | Payload                                     |
|------|---------------|----------|---------------------------------------------|
| 1    | Host → gun    | `0x0026` | `35`                                        |
| 2    | Gun → host    | `0x0023` | `35 00 0a 02 02 01 00 0a LL NN MM 00 0a`    |
| 3    | Host → gun    | `0x0026` | `5b XX`  (XX = persisted volume, e.g. `1f`) |

- Step 1 is a startup query/init request. **Confidence: confirmed**.
- Step 2 is the gun's identity/config snapshot. **Confidence: confirmed structure; field names inferred**.
- Step 3 sets the initial volume to the app-persisted value. **Confidence: confirmed** (Tests 4 and 6).

---

## Known Message Types

### `35` — Startup Query (host → gun)

Single byte `35` on handle `0x0026`. Triggers the gun startup snapshot response.

---

### `35 ...` — Startup Snapshot (gun → host)

13-byte notification on handle `0x0023`.

```
35 00 0a 02 02 01 00 0a  LL  NN  MM  00  0a
 0  1  2  3  4  5  6  7   8   9  10  11  12
```

| Byte | Symbol | Meaning                        | Confidence |
|------|--------|--------------------------------|------------|
| 0    | `35`   | Message ID                     | Confirmed  |
| 1    | `00`   | Fixed / reserved               | Confirmed  |
| 2    | `0a`   | Fixed marker                   | Inferred   |
| 3    | `02`   | Fixed protocol/group field     | Inferred   |
| 4    | `02`   | Fixed protocol/group field     | Inferred   |
| 5    | `01`   | Startup subcommand / mode      | Inferred   |
| 6    | `00`   | Fixed / reserved               | Confirmed  |
| 7    | `0a`   | Fixed marker                   | Inferred   |
| 8    | `LL`   | Persistent level               | High       |
| 9    | `NN`   | Name part 1 (option field A)   | Inferred   |
| 10   | `MM`   | Name part 2 (option field B)   | Inferred   |
| 11   | `00`   | Fixed / reserved               | Confirmed  |
| 12   | `0a`   | Fixed terminator               | Inferred   |

Observed startup snapshots across Test 1:

| Gun | Payload                          | Notes                        |
|-----|----------------------------------|------------------------------|
| g0  | `35000a020201000a031732000a`      | level 3, name parts 0x17/0x32 |
| g1  | `35000a020201000a020f0f000a`      | level 2, name parts 0x0f/0x0f |
| g2  | `35000a020201000a000000000a`      | level 0 (unnamed in app)     |
| g3  | `35000a020201000a023231000a`      | level 2, name parts 0x32/0x31 |

Test 6 (gun 0, now level 4):

```
35000a020201000a041214000a
```

---

### `36 ...` — Config Write (host → gun)

13-byte command on handle `0x0026`. Writes the gun's level and name configuration.

Observed forms:

| Form | Payload pattern                         | When observed              |
|------|-----------------------------------------|----------------------------|
| A    | `36 00 0a 02 02 01 00 0a LL NN MM 00 0a` | Baseline / most tests      |
| B    | `36 00 0a 02 02 03 00 0a LL NN MM 00 04` | Later phase of some tests  |
| C    | `36 00 0d 03 02 03 00 0f LL NN MM 00 VV` | Level 4+ state (Test 6/7)  |

Field mapping for byte 8 (`LL`) and bytes 9–10 (`NN MM`) — same layout as the startup snapshot.

#### g0 level progression across all tests

Gun 0 started at level 3 (visible in Test 1 captures) and progressed to level 5 by Test 7.  Tracking how the config write changed reveals which bytes encode level vs. state:

| Test(s) | Level | Upgrades allocated | Example config write payload |
|---------|-------|--------------------|------------------------------|
| 1–5     | 3     | Health×1, Munition×1, Damage×1 (+ Power-Up Attack) | `36000a020203000a031214000[3/4]` |
| 6       | 4     | Health×1, Munition×1, Damage×1, Reload speed×1     | `36000d030203000f0412140004`      |
| 7       | 5     | Health×1, Ammunition×1, Damage×1, Reactivation time×1 | `36000d030203000f0512140003`   |

Byte-level deltas when level increased 3 → 4 (Test 6 vs. Test 5):

| Byte | Test 5 value | Test 6 value | Note |
|------|-------------|-------------|------|
| 2    | `0a`        | `0d`        | Changed with level-4 state |
| 3    | `02`        | `03`        | Changed with level-4 state |
| 7    | `0a`        | `0f`        | Changed with level-4 state |
| 8    | `03`        | `04`        | Level byte `LL` |
| 12   | `04`        | `04`        | Unchanged (form B) |

At level 5 (Test 7) all three forms (A, B, C) reappear; the trailing byte in form C shifts from `04` to `03`.  Bytes 2, 3, and 7 likely encode progression-dependent parameters (possibly related to upgrade count or type), but their exact meaning is **inferred**.

Other guns from Test 1 (no later progression data available):

| Gun | Configured level | `LL` byte | Upgrades allocated |
|-----|------------------|-----------|--------------------|
| g0  | 3                | `03`      | Health×1, Munition×1, Damage×1 |
| g1  | 2                | `02`      | Damage×1 |
| g2  | 1                | `01`      | None |
| g3  | 2                | `02`      | Reload speed×1 |

#### Name-part bytes

Observed name-part bytes for configured guns (from Test 1):

| Gun | App-displayed name | Protocol byte `NN` | Protocol byte `MM` | Inferred first-word list position | Inferred second-word list position |
|-----|--------------------|--------------------|--------------------|---------------------------------|----------------------------------|
| g0  | Hurricane Howler   | `12` (18)          | `14` (20)          | 17                              | 19                               |
| g1  | Air Blaze          | `02` (2)           | `04` (4)           | 1                               | 3                                |
| g2  | Atom Beast         | `03` (3)           | `05` (5)           | 2                               | 4                                |
| g3  | Burst Defender     | `04` (4)           | `0a` (10)          | 3                               | 9                                |

The protocol byte values are **confirmed** from captures.  The "inferred list position" column is byte − 1 in both cases.

The original test log recorded "Index 2" for g3's first name ("Burst"), which would predict byte `03`; the actual captured byte is `04`.  The captures are authoritative; the test log entry appears to have a transcription error.  Comparing g2 and g3 on the first-name word list: "Atom" → byte `03` (list position 2), "Burst" → byte `04` (list position 3), consistent with an alphabetically ordered list.

The app uses **separate** word lists for the first and second name words, each with independent indices.

#### Observed name byte range (highest observed values)

The startup snapshot (35...) carries the *pre-existing* name stored on the gun.  Three guns in Test 1 already had names before being renamed, giving the highest observed name bytes:

| Gun | Pre-existing app name | Startup NN (first-name byte) | Startup MM (second-name byte) |
|-----|-----------------------|------------------------------|-------------------------------|
| g0  | Laser Zombie          | `0x17` (23)                  | `0x32` (50)                   |
| g1  | Frost Falcon          | `0x0f` (15)                  | `0x0f` (15)                   |
| g3  | Zinc Zenith           | `0x32` (50)                  | `0x31` (49)                   |

Highest first-name byte observed across all tests: **`0x32` = 50** ("Zinc", g3 startup, Test 1).  
Highest second-name byte observed across all tests: **`0x32` = 50** ("Zombie", g0 startup, Test 1).

> **Note:** The protocol byte is an 8-bit field so values up to `0xff` are technically sendable, but the app's name-word lists are finite.  The highest value ever observed in any capture is `0x32` (50).  Bytes above `0x32` have never been seen and very likely do not map to valid words in the app; sending them may cause undefined behavior on the gun.

#### Fixed bytes and upgrade-count correlation in `35 ...` and `36 ...`

Startup snapshot (`35 ...`):  
Bytes 2, 3, 4, 5, 7, 12 (`0a 02 02 01 0a 0a`) are **constant** across all observed startup payloads, regardless of gun level or upgrade count.  Only bytes 8–10 (`LL NN MM`) vary.

Config write (`36 ...`):  
Forms A and B share the same bytes 2, 3, 7 (`0a`, `02`, `0a`).  These are constant for all four Test 1 guns — level 1, 2, and 3, with 0–3 upgrades — confirming they do **not** vary per-gun or per-upgrade within that level range.  Form C, which only appears at level 4+, uses different values for those bytes:

| Byte position | Forms A/B (level 1–3) | Form C (level 4+) | Change |
|---------------|-----------------------|-------------------|--------|
| 2             | `0a` (10)             | `0d` (13)         | +3     |
| 3             | `02`  (2)             | `03`  (3)         | +1     |
| 7             | `0a` (10)             | `0f` (15)         | +5     |

The transition from (0a, 02, 0a) to (0d, 03, 0f) is observed when g0 advances from level 3 (3 upgrades) to level 4 (4 upgrades).  At level 5 (still 4 upgrades of different types) these bytes remain at (0d, 03, 0f), so the change is not driven solely by upgrade type.  Whether the trigger is the **level threshold** or the **4th upgrade slot** being filled cannot be determined from the available captures; a minimal capture comparing a level-4 gun before and after its 4th upgrade would be needed to disambiguate.  **Confidence: inferred.**

---

### `57` — Apply / Commit (host → gun)

Single byte `57` on handle `0x0026`. Sent after config writes. **Confidence: confirmed placement; inferred meaning**.

---

### `5b XX` — Volume Set (host → gun)

Two bytes on handle `0x0026`.

| Byte | Value range | Meaning                              |
|------|-------------|--------------------------------------|
| 0    | `5b`        | Command ID                           |
| 1    | `00`–`1f`   | Volume intensity (0 = mute, 31 = max) |

The byte is a **continuous linear slider position** (0–31).  The app sends real-time position updates as the user drags the slider; intermediate values are not fixed discrete steps.  **Confidence: confirmed** (Tests 3 and 4).

Startup default: `5b1f` (max volume, or whatever the app has persisted — e.g. `5b00` after user muted; confirmed in Test 6).

Volume control is only accessible during an active game session.

---

### `51` — Status Poll (host → gun)

Single byte `51` on handle `0x0026`. Sent periodically (~every 27 s on average). **Confidence: high**.

---

### `51 XX YY` — Status Reply (gun → host)

Three-byte notification on handle `0x0023`. Response to the status poll.

| Byte | Symbol | Meaning              | Confidence |
|------|--------|----------------------|------------|
| 0    | `51`   | Message ID           | Confirmed  |
| 1    | `XX`   | Status word byte 1   | Inferred   |
| 2    | `YY`   | Status word byte 2   | Inferred   |

Observed examples:

- g0: `510332`, `510333`, `510334`, `510335`
- g1: `5102bf`, `5102c2`, `5102c3`
- g2: `51033e`, `51033f`, `510340`
- g3: `5102b9`, `5102bb`

The 16-bit word in bytes 1–2 drifts upward over time. Likely contains a battery or status component; polarity/semantics not yet proven.

---

### `49` — Trigger / Fire Event (gun → host)

Single byte `49` on handle `0x0023`. One notification per trigger pull. **Confidence: high**.

Minimum prerequisites before `49` appears in captures: active BLE connection + notification setup + startup exchange (`35` / `35...` / `5bXX`).

---

### `52` — Reload Marker A (gun → host)

Single byte `52` on handle `0x0023`. **Confidence: medium**. Always followed ~0.5 s later by `310a` (or `310d` in newer firmware/level mode).

---

### `310a` / `310d` — Reload Marker B (gun → host)

Two-byte notification on handle `0x0023`. Pairs 1:1 with `52` in gameplay captures.

| Value  | Context                              | Confidence |
|--------|--------------------------------------|------------|
| `310a` | Older mode (Tests 1–6)               | Medium     |
| `310d` | Newer mode (Test 7, level 5)         | Medium     |

---

### `32 XX ...` — Ammo / Shot State (gun → host)

Variable-length notification on handle `0x0023`. Appears after each trigger event.

Observed families:

| Prefix | Mode          | Confidence  |
|--------|---------------|-------------|
| `3202` | Older mode    | Medium-High |
| `320a` | Older mode    | Medium-High |
| `3203` | Newer mode    | Medium-High |
| `320e` | Newer mode    | Medium-High |

The last byte appears to be a counter that decrements per shot. Exact semantics inferred.

---

### `37 0a 01 00` / `37 0e 01 00` — In-Game Control (host → gun)

Four-byte command on handle `0x0026`. Observed during gameplay; possibly a reload/special-shot state transition.

| Payload       | Mode observed         | Confidence |
|---------------|-----------------------|------------|
| `370a0100`    | Older mode (Tests 2–6)| Medium     |
| `370e0100`    | Newer mode (Test 7)   | Medium     |

---

### Game Setup Commands (host → gun, observed in Test 2)

The following host→gun commands were seen during the AR game setup phase. Their exact semantics are **low-to-medium confidence**:

| Payload                       | Count | Candidate meaning             |
|-------------------------------|------:|-------------------------------|
| `4401`                        | 1     | Game mode init flag           |
| `490100`                      | 1     | Game option toggle/flag       |
| `4a0000000000000000001388`    | 1     | Timed/parameterised game setup |
| `411388`                      | 1     | Setup parameter (paired with `4a`) |
| `3b07`                        | 1     | Setup parameter               |
| `390a`                        | 1     | Setup parameter               |

---

### `5a 3f 01 TT 00 00` — End-of-Game Stat Request (host → gun)

Six-byte command on handle `0x0026`. Sent multiple times at end of game.

| Byte | Symbol | Meaning      | Confidence |
|------|--------|--------------|------------|
| 0–2  | `5a3f01` | Command prefix | Inferred |
| 3    | `TT`   | Stat class/type (01, 02, or 06 observed) | Inferred |
| 4–5  | `0000` | Fixed zero   | Confirmed  |

---

### `30 01 3f TT NN` — End-of-Game Stat Counter (gun → host)

Five-byte notification on handle `0x0023`.

| Byte | Symbol | Meaning                                   | Confidence |
|------|--------|-------------------------------------------|------------|
| 0–2  | `30013f` | Response prefix                         | Confirmed  |
| 3    | `TT`   | Stat class/type (matches request)         | Inferred   |
| 4    | `NN`   | Counter / progress value (descends to 00) | Inferred   |

Observed upper-bound values for `NN`:
- Tests 2–3 (level 3): upper bound `09`
- Test 6 (level 4): upper bound `0e`
- Test 7 (level 5): values `00 04 05 06 07 0e` observed in a multi-round capture

The upper bound grows with level/upgrades progression.

---

### `3e 01 00` — End-of-Game Terminal Marker (gun → host)

Three-byte notification on handle `0x0023`. Signals completion of the end-of-game stat exchange. **Confidence: medium**.

---

### `42` — Session Close (host → gun)

Single byte `42` on handle `0x0026`. Final command sent at the end of a session. **Confidence: low-medium**.

---

## Mode Shift (Older vs. Newer)

Tests 6/7 show that certain message families changed from an `0x0a`-series to an `0x0d`/`0x0e`-series after level 5 / upgrade changes:

| Family         | Older mode (Tests 1–6) | Newer mode (Test 7)  |
|----------------|------------------------|----------------------|
| Reload pair    | `52` + `310a`          | `52` + `310d`        |
| Ammo state     | `3202xx` / `320axx`    | `3203xx` / `320exx`  |
| In-game ctrl   | `370a0100`             | `370e0100`           |

**Confidence: medium.** The trigger is not fully isolated — both a level change and an upgrade-slot change occurred between these test groups.

