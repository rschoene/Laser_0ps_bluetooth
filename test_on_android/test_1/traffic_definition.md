# Traffic Definition

This file defines the currently understood BLE application traffic from [test_1.md](test_1.md) and [filtered_.log](filtered_.log).

Confidence markers:
- Confirmed: directly observed multiple times in the capture.
- Inferred: consistent with the capture, but meaning is not fully proven yet.

## Transport

- ATT Write Command from host to gun: opcode `0x52`, usually on handle `0x0026`
- ATT Notification from gun to host: opcode `0x1b`, usually on handle `0x0023`
- ATT Write Request during setup: opcode `0x12`, seen on handle `0x0024`

## Startup Sequence

Observed order for each gun session:

1. Host sends `35` to handle `0x0026`.
2. Gun responds with a 13-byte `35 ...` payload on handle `0x0023`.
3. Host sends `5b xx` to handle `0x0026`.

Current interpretation:

- Step 1 is a startup query or init request. Confirmed.
- Step 2 is the gun's identity/config snapshot. Confirmed.
- Step 3 is the initial volume set to the app-persisted value. Confirmed.

Example from gun 0:

- Host -> gun, handle `0x0026`: `35`
- Gun -> host, handle `0x0023`: `35 00 0a 02 02 01 00 0a 03 17 32 00 0a`
- Host -> gun, handle `0x0026`: `5b 1f`

## Message Types

### 1. Host init request

- Direction: host -> gun
- Handle: `0x0026`
- Payload: `35`
- Length: 1 byte
- Meaning: session startup query/request
- Confidence: Confirmed for placement in sequence, inferred for semantic label

Byte layout:

| Byte | Value | Meaning |
|---|---|---|
| 0 | `35` | init/startup command id |

### 2. Gun startup snapshot

- Direction: gun -> host
- Handle: `0x0023`
- Payload form (baseline): `35 00 0a 02 02 01 00 0a LL NN MM 00 0a`
- Alternate observed form (Test 10): `35 00 12 01 02 00 01 0a LL NN MM 00 0a`
- Length: 13 bytes
- Meaning: gun identity/config snapshot at startup
- Confidence: Confirmed for structure, partially inferred for field names

Byte layout:

| Byte | Symbol | Meaning | Confidence |
|---|---|---|---|
| 0 | `35` | startup snapshot message id | Confirmed |
| 1 | `00` | fixed/reserved | Confirmed |
| 2–7 | — | template-dependent framing bytes; not live health/ammo | High |
| 8 | `LL` | level, or level echo when populated | High |
| 9 | `NN` | name part 1 / option field A | Inferred |
| 10 | `MM` | name part 2 / option field B | Inferred |
| 11 | `00` | fixed/reserved | Confirmed |
| 12 | `0a` | fixed terminator | High |

Observed startup snapshots:

- Gun 0: `35 00 0a 02 02 01 00 0a 03 17 32 00 0a`
- Gun 1: `35 00 0a 02 02 01 00 0a 02 0f 0f 00 0a`
- Gun 2: `35 00 0a 02 02 01 00 0a 00 00 00 00 0a`
- Gun 3: `35 00 0a 02 02 01 00 0a 02 32 31 00 0a`
- Test 10 alternate profile: `35 00 12 01 02 00 01 0a 02 27 04 00 0a`

Notes:

- Gun 2 reports `00 00 00` in bytes 8..10 at startup, which matches it appearing unnamed in the app.
- Guns 0, 1, and 3 appear to echo a meaningful value at byte 8 that matches the configured level.
- In the baseline template, bytes 2 and 7 remain `0a` even at levels 4 and 5 (confirmed in Tests 6 and 7), whereas the corresponding positions in the `36...` form C config write change to `0d`/`0f` at level 4+. They do not encode current health or ammo.
- Test 10 proves bytes 2–7 are not globally fixed; they are template-dependent framing bytes.

### 3. Host volume set (initial persisted value)

- Direction: host -> gun
- Handle: `0x0026`
- Payload: `5b xx`
- Length: 2 bytes
- Meaning: set initial gun volume to the app-persisted/current value
- Confidence: Confirmed (Tests 4 and 6)

Byte layout:

| Byte | Value | Meaning |
|---|---|---|
| 0 | `5b` | command id: set volume |
| 1 | `xx` | volume intensity byte (0x00 = mute, 0x1f = max) |

Observed startup examples:
- Test 4: `5b1f` (default/high volume)
- Test 6: `5b00` (persisted muted volume)

### 4. Host config write

- Direction: host -> gun
- Handle: `0x0026`
- Payload form A: `36 00 0a 02 02 01 00 0a LL NN MM 00 0a`
- Payload form B: `36 00 0a 02 02 03 00 0a LL NN MM 00 04`
- Alternate observed forms (Test 10): `36 00 12 01 02 00 01 0a LL NN MM 00 0a`, `36 00 12 01 03 03 01 0a LL NN MM 00 04`, `36 00 12 02 03 03 01 0a LL NN MM 00 04`
- Length: 13 bytes
- Meaning: level + name/config write
- Confidence: Confirmed for structure, high confidence for level byte

Byte layout:

| Byte | Symbol | Meaning | Confidence |
|---|---|---|---|
| 0 | `36` | config write message id | Confirmed |
| 1 | `00` | fixed/reserved | Confirmed |
| 2 | `0a` | fixed delimiter or marker | Inferred |
| 3 | `02` | fixed protocol/group field | Inferred |
| 4 | `02` | fixed protocol/group field | Inferred |
| 5 | `01` or `03` | subcommand / phase selector | High |
| 6 | `00` | fixed/reserved | Confirmed |
| 7 | `0a` | fixed delimiter or marker | Inferred |
| 8 | `LL` | level | High |
| 9 | `NN` | name part 1 / option field A | Inferred |
| 10 | `MM` | name part 2 / option field B | Inferred |
| 11 | `00` | fixed/reserved | Confirmed |
| 12 | `0a` or `04` | trailing mode/apply selector | High |

Confirmed level mapping from notes:

- Gun 0 level 3 -> `03`
- Gun 1 level 2 -> `02`
- Gun 2 level 1 -> `01`
- Gun 3 level 2 -> `02`

Observed variable bytes for configured guns:

- Gun 0: `03 12 14`
- Gun 1: `02 02 04`
- Gun 2: `01 03 05`
- Gun 3: `02 04 0a`

Current interpretation:

- Byte 8 is level.
- Bytes 9 and 10 are the two selected name/identity parts.

### 5. Host apply/commit command

- Direction: host -> gun
- Handle: `0x0026`
- Payload: `57`
- Length: 1 byte
- Meaning: likely apply/commit after config write
- Confidence: Confirmed for placement, inferred for meaning

Byte layout:

| Byte | Value | Meaning |
|---|---|---|
| 0 | `57` | apply/commit command id |

### 6. Host status poll

- Direction: host -> gun
- Handle: `0x0026`
- Payload: `51`
- Length: 1 byte
- Meaning: periodic poll/status request
- Confidence: High

Byte layout:

| Byte | Value | Meaning |
|---|---|---|
| 0 | `51` | poll/status request command id |

Observed cadence:

- approximately every 27 seconds on average during the active session

### 7. Gun status reply

- Direction: gun -> host
- Handle: `0x0023`
- Payload form: `51 XX YY`
- Length: 3 bytes
- Meaning: status snapshot / counter value
- Confidence: Confirmed for structure, inferred for exact semantics

Byte layout:

| Byte | Symbol | Meaning | Confidence |
|---|---|---|---|
| 0 | `51` | status reply id | Confirmed |
| 1 | `XX` | state value byte 1 | Inferred |
| 2 | `YY` | state value byte 2 | Inferred |

Observed values:

- Gun 0: `51 03 32`, `51 03 33`, `51 03 34`, `51 03 35`
- Gun 1: `51 02 bf`, `51 02 c2`, `51 02 c3`
- Gun 2: `51 03 3e`, `51 03 3f`, `51 03 40`
- Gun 3: `51 02 b9`, `51 02 bb`

### 8. Gun trigger event

- Direction: gun -> host
- Handle: `0x0023`
- Payload: `49`
- Length: 1 byte
- Meaning: trigger/fire event
- Confidence: High

Byte layout:

| Byte | Value | Meaning |
|---|---|---|
| 0 | `49` | trigger/fire event id |

Prerequisites before `49` can appear:

1. BLE link and ATT setup must already be active.
2. Notifications on the `0x0023` path are likely enabled first via the setup write on handle `0x0024`.
3. The startup exchange is observed before any `49` in this capture:
	- host `35` on `0x0026`
	- gun `35 00 0a 02 02 01 00 0a LL NN MM 00 0a` on `0x0023`
	- host `5b 1f` on `0x0026`

What does not appear to be required before `49`:

- the later `36 ...` config writes
- the `57` apply command
- the periodic `51` / `51 XX YY` poll and status exchange

Current interpretation:

- Minimum likely requirement is: connection + notification enable + initial `35 / 35... / 5b1f` startup exchange.
- Exact necessity of each step is still inferred from ordering, not yet proven by a negative test.

Observed counts in this capture:

- Gun 0: 3
- Gun 1: 4
- Gun 2: 0
- Gun 3: 10

## Single-Player AR Extensions (Test 2)

Source:
- [../test_2/test_2.md](../test_2/test_2.md)
- [../test_2/filtered_.log](../test_2/filtered_.log)

Scope:
- Single gun session (gun 0 only)
- Single-player AR mode with repeated shooting, reload behavior, and end-of-round progression

### What stayed the same vs baseline

1. Startup still begins with:
	- host `35` on `0x0026`
	- gun `35 00 0a 02 02 01 00 0a ... 00 0a` on `0x0023`
	- host `5b1f` on `0x0026`
2. Trigger event `49` on handle `0x0023` is still present and dominant during gameplay.

### New host -> gun commands on `0x0026` (Test 2)

Observed values and current interpretation:

| Payload | Count | Candidate meaning | Confidence |
|---|---:|---|---|
| `370a0100` | 6 | in-game control action, likely reload/special-shot state transition | Medium |
| `4401` | 1 | game mode init/config flag | Low-Medium |
| `490100` | 1 | game option toggle/flag set | Low-Medium |
| `4a0000000000000000001388` | 1 | timed/parameterized game setup value | Low |
| `411388` | 1 | setup parameter paired with `4a...` | Low |
| `3b07` | 1 | setup parameter (possibly countdown/sound/game mode) | Low |
| `390a` | 1 | setup parameter (possibly countdown/sound/game mode) | Low |
| `5a3f01010000` | 5 | apply 1 damage during end-game HP synchronization | High |
| `5a3f01020000` | 3 | apply 2 damage during end-game HP synchronization | High |
| `42` | 1 | final session close/ack command | Low-Medium |

### New gun -> host notifications on `0x0023` (Test 2)

Observed values and current interpretation:

| Payload pattern | Count | Candidate meaning | Confidence |
|---|---:|---|---|
| `49` | 41 | trigger/fire event | High |
| `3202xx` / `320axx` | many | per-shot ammo/counter/state update family | Medium-High |
| `52` | 4 | reload/sound lifecycle marker part 1 | Medium |
| `310a` | 4 | reload/sound lifecycle marker part 2 | Medium |
| `30013f....` | 6 | remaining HP after applying requested damage | High |
| `3e0100` | 1 | end-of-round terminal marker | Medium |

### Strong sequencing pattern discovered

In four repeated cases, gun notification `52` is followed about 0.5 seconds later by `310a`.

Interpretation:
- `52` and `310a` likely belong to a paired lifecycle event (reload/sound/cycle-complete).
- This pattern was not present in the simpler baseline flow from Test 1.

### Unknown-gun startup check in Test 2

Not observed in Test 2 capture:
- The startup payload `35 00 0a 02 02 01 00 0a 00 00 00 00 0a` did not appear.

Observed instead:
- gun 0 startup payload carried non-zero tuple `... 03 12 14 ...`.

Interpretation:
- In this run, gun 0 did not present as unknown on startup.

### Practical decoding guidance for next captures

To further split reload vs sound vs progression semantics:

1. Perform a run with shooting only and no manual reload if possible.
2. Perform a run with forced frequent reload and minimal shooting.
3. Perform a run that reaches end screen quickly (for xp/result messages).
4. Compare deltas for these message families first:
	- host: `370a0100`, `5a3f01010000`, `5a3f01020000`
	- gun: `52`, `310a`, `3202xx/320axx`, `30013f....`, `3e0100`

## Single-Player AR No-Reload + Volume Sweep (Test 3)

Source:
- [../test_3/test_3.md](../test_3/test_3.md)
- [../test_3/filtered_.log](../test_3/filtered_.log)

Scope:
- Single gun session (gun 0 only)
- Shooting without manual reload
- Pause and lower gun volume in steps

### Confirmed differences vs Test 2

1. Trigger event `49` is present (10 occurrences in this run).
2. Reload-like gun notification pair from Test 2 is absent:
   - no `52` notifications
   - no `310a` notifications

Interpretation:
- This strengthens the hypothesis that `52` + `310a` belong to reload/sound-cycle signaling associated with the reload flow.

### Volume control: `5bxx` — CONFIRMED (Test 4)

- Direction: host -> gun
- Handle: `0x0026`
- Command byte: `5b`
- Parameter byte `xx`: raw linear intensity, `0x00` (mute) – `0x1f` (max = 31)

The byte `xx` is a **continuous slider position** (0–31). The app sends real-time position updates as the user drags the slider; intermediate values vary between sweeps at the same speed. The endpoints are stable:

| `xx` | Decimal | Meaning |
|---|---|---|
| `00` | 0 | mute / minimum |
| `1f` | 31 | maximum (also sent at startup) |

Observed values across all tests: `00 02 03 04 06 07 09 0a 0b 0f 10 11 14 15 18 19 1b 1f`

Test 4 sweep data (three sweeps, game running, no shooting):

| Sweep | Direction | Values |
|---|---|---|
| startup | — | `5b1f` |
| sweep 1 | 10→0 | `5b19 5b15 5b10 5b0b 5b07 5b04 5b00` |
| sweep 2 | 0→10 | `5b02 5b03 5b06 5b0a 5b0f 5b14 5b18 5b1b 5b1f` |
| sweep 3 | 10→0 | `5b19 5b15 5b0f 5b0b 5b03 5b00` |

Note: volume controls require an active game session — they are unavailable outside gameplay.

Current confidence:
- `5bxx` as volume-control family: **Confirmed**
- `xx` = continuous intensity 0–31: **Confirmed**
- exact UI-level-to-`xx` mapping: not pinned (continuous slider)

### Test 3 message highlights

Host -> gun notable values:
- `5b19`, `5b11`, `5b09`, `5b02`, `5b00` (volume phase)
- `370a0100` (still present, but fewer times than Test 2)
- `5a3f01010000` (end-of-round/stat sync)

Gun -> host notable values:
- `49` (trigger)
- `3202xx` / `320axx` (shot/state updates)
- `30013f0109` down to `30013f0100` (remaining HP after repeated 1-damage sync on a 10-HP gun)
- `3e0100` (terminal marker)

### Updated practical guidance

To finalize volume decoding:

1. Perform a short run with no gameplay events after connection.
2. Change only volume 10 -> 0 with 2-3 seconds pause per step.
3. Record exact UI level and timestamp per step.
4. Extract only host `5bxx` writes and build exact lookup: UI level -> `xx`.

## Working Sequence Model

Current best sequence model:

1. Host writes `35` to `0x0026`.
2. Gun notifies `35 00 0a 02 02 01 00 0a LL NN MM 00 0a` on `0x0023`.
3. Host writes `5b xx` to `0x0026` (initial volume set from persisted app state).
4. Later, host writes `36 ...` config frames and `57` apply frames.
5. During operation, host polls with `51` and gun responds with `51 XX YY`.
6. Gun emits `49` whenever the trigger/fire event occurs.

This matches your current assumption well:

- `35` on handle `0x0026` is host-sent.
- `35 ...` on handle `0x0023` is gun-sent.
- `5bxx` on handle `0x0026` follows immediately — sets initial volume to the persisted current setting.

## Volume Sweep (Test 4)

Source:
- [../test_4/test_4.md](../test_4/test_4.md)
- [../test_4/filtered_.log](../test_4/filtered_.log)

Scope:
- Single gun (gun 0), game started (required to access volume controls), no shooting
- Three sweeps: down (10→0), up (0→10), down (10→0)

### Confirmed: `5bxx` = set volume

The volume byte `xx` is a **continuous linear intensity** from `0x00` (mute) to `0x1f` (max, 31 decimal).
The app sends slider position in real time — intermediate values differ between sweeps at the same UI speed,
confirming this is a continuous control, not discrete fixed steps.

Endpoints are stable and confirmed across all tests:
- `5b00` → mute / minimum
- `5b1f` → maximum (also sent at startup = default max volume)

See the `5bxx` entry in the message-type section above for full sweep data.

### Updated working sequence model step 3

Step 3 is now confirmed as a volume set (not a session enable or handshake):

> 3. Host writes `5b xx` to `0x0026` → sets volume to persisted current value.

`5b1f` is now interpreted as one specific volume value (max), not a universal startup constant.

## Level 4 Sync / Upgrade-State Delta (Test 6)

Source:
- [../test_6/test_6.md](../test_6/test_6.md)
- [../test_6/filtered_.log](../test_6/filtered_.log)

Pre-state:
- level: 4
- upgrades: health=1, munition=1, damage=1, reload=1
- no gameplay interaction during the test

### Confirmed state-report change (`35...`)

- Test 5 startup snapshot: `35000a020201000a031214000a`
- Test 6 startup snapshot: `35000a020201000a041214000a`

Only the level byte changed in this field from `03` to `04`, confirming `LL` as persistent level.

### Confirmed state-write change (`36...`)

- Previous baseline write: `36000a020203000a0312140004`
- Test 6 write: `36000d030203000f0412140004`

Changed bytes:
- byte 2: `0a -> 0d`
- byte 3: `02 -> 03`
- byte 7: `0a -> 0f`
- byte 8 (`LL`): `03 -> 04`

Interpretation:
- `36...` is state/config write from host to gun.
- `35...` is state report from gun to host.
- Additional byte deltas besides `LL` likely encode progression-dependent parameters (possibly upgrade-related fields).

### End/stat sequence range changed

- Earlier runs: `30013f0109` down to `30013f0100`
- Test 6: `30013f010e` down to `30013f0100`

This matches the UI change from 10 life to 15 life: the reply is best read as remaining HP after each 1-damage end-of-game sync step.

## Level-5 Transition / Upgrade Delta (Test 7)

Source:
- [../test_7/test_7.md](../test_7/test_7.md)
- [../test_7/filtered_.log](../test_7/filtered_.log)

Observed structure:
- The capture contains an early phase still reporting level 4, then a later phase where level-5 writes appear.

### Early phase (level 4 still active)

- startup report: `35000a020201000a041214000a`
- state/config write: `36000d030203000f0412140003`
- startup volume write remains persisted: `5b00`

### Later phase (level 5 synchronized)

New host `36...` writes include `...051214...`:
- `36000a020201000a051214000a`
- `36000a020203000a0512140004`
- `36000d030203000f0512140003`

Interpretation:
- Level transition to 5 is encoded in the same state byte position (`LL`) as prior level transitions.
- `35...` remains the report frame; `36...` remains the write frame.

### New gameplay-family prefixes in Test 7

Compared to older runs (`3202/320a`, `310a`, `370a0100`), Test 7 shows:
- `3203xx` and `320exx`
- `310d` (instead of `310a`)
- `370e0100` (instead of `370a0100`)

This suggests one or more progression-dependent mode/version parameters shifted from `0x0a`-series to `0x0d`/`0x0e`-series in the new state.

Later evidence from Test 10 adds another profile-dependent family:

- startup snapshot template `350012010200010a...`
- config write template `360012...`
- reload marker `3112`
- in-game control `37040100`
- ammo-state frame `320409`

### Important caution

Test 7 is not a single minimal no-interaction round; it contains substantial gameplay traffic and multiple phases.
For strict per-byte attribution to exactly one upgrade choice, run a minimal level-5 no-interaction capture after confirming level 5 at connection time.