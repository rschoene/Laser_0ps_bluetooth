# Test 9: Two-Blaster Multiplayer - Protocol Analysis

## Test Overview

- **Scenario**: two connected blasters, 3-minute multiplayer game, repeated twice
- **Capture evidence**: two startup snapshots, two game-start sequences, and two end-of-game stat exchanges
- **Important correction**: this is **not** a single-player AR duel

The handwritten notes in [test_9.md](test_9.md) describe two multiplayer rounds with two blasters, where one blaster fires 30 shots with 10 hits / 2 kills in round 1, then 10 shots with 7 hits / 1 kill in round 2. The filtered BLE traffic matches that structure closely.

## What Is Actually In The Capture

Observed payload families in Test 9:

- `35` and `35...` startup query / snapshot
- `49...` per-blaster pre-game assignment/config packets
- `4a000aff00b4000000002710` game configuration
- `5b00` volume set
- `58` game arm/start
- `42` end-of-game close
- `47....` end-of-game per-blaster aggregate counter
- `54..` end-of-game per-slot stat query and reply

Notably, there are **no `51` packets on the main command/notification handles** in this filtered Test 9 stream. The earlier `51 = gameplay polling` claim was too aggressive. Per [protocol_definition.json](../../definition_protocol/protocol_definition.json), `51` is better treated as a likely battery/status exchange, and it is not needed to explain the multiplayer round flow in this test.

## Round 1 Sequence

### Round 1 Setup

- `7.428s` host → blaster A: `490200`
- `7.547s` host → blaster A: `4a000aff00b4000000002710`
- `7.666s` host → blaster A: `5b00`
- `7.786s` host → blaster A: `35`
- `7.825s` blaster A → host: `35000a020201000a020204000a`
- `7.986s` host → blaster A: `58`

- `15.487s` host → blaster B: `490301`
- `15.607s` host → blaster B: `4a000aff00b4000000002710`
- `15.726s` host → blaster B: `5b00`
- `15.846s` host → blaster B: `35`
- `15.887s` blaster B → host: `35000a020201000a051214000a`
- `16.046s` host → blaster B: `58`

### Round 1 End-Of-Round Exchange

- `213.082s` blaster B → host: `47001e`
- `213.222s` host → one blaster: `42`
- `213.316s` blaster A → host: `470000`
- `213.342s` host → query: `5402`
- `213.401s` reply: `5400000002`
- `213.462s` host → second close: `42`
- `213.582s` host → query: `5403`
- `213.618s` reply: `54000a0203`

### Round 1 Interpretation

- `47001e` is a strong match for the handwritten note “shoots (30 times)” because `0x001e = 30`
- `54000a0203` is a strong match for the handwritten round-1 result “hits 10 times, kills 2 times” because the middle bytes are `0x0a` and `0x02`
- `470000` from the other blaster matches the loser’s `0` hits / `0` kills line in the note

The safest interpretation is:

- `47` carries a **per-blaster aggregate shot count** for the completed round
- `54` replies carry **per-slot round stats**, with the last byte echoing the queried slot/index

Important ordering note:

- `47` is part of the round-close sequence, but not strictly before or after `42`
- Test 8 shows the same interleaving behavior, so the robust conclusion is that `47`, `42`, and `54` belong to the same end-of-round exchange

## Round 2 Sequence

### Round 2 Setup

- `409.049s` host → blaster A: `490400`
- `409.170s` host → blaster A: `4a000aff00b4000000002710`
- `409.288s` host → blaster A: `5b00`
- `409.328s` host → blaster B: `490501`
- `409.408s` host → blaster A: `35`
- `409.452s` blaster A → host: `35000a020201000a020204000a`
- `409.448s` host → blaster B: `4a000aff00b4000000002710`
- `409.567s` host → blaster B: `5b00`
- `409.608s` host → blaster A: `58`
- `409.687s` host → blaster B: `35`
- `409.729s` blaster B → host: `35000a020201000a051214000a`
- `409.887s` host → blaster B: `58`

### Round 2 End-Of-Round Exchange

- `606.543s` blaster B → host: `47000a`
- `606.690s` host → close: `42`
- `606.811s` host → query: `5404`
- `606.914s` reply: `5400000004`
- `607.660s` blaster A → host: `470000`
- `607.807s` host → close: `42`
- `607.926s` host → query: `5405`
- `607.978s` reply: `5400070105`

### Round 2 Interpretation

- `47000a` is a strong match for the handwritten note “shoots (10 times)” because `0x000a = 10`
- `5400070105` is a strong match for the handwritten round-2 result “hits 7 times, kills 1 times” because the middle bytes are `0x07` and `0x01`
- Again, the opposing blaster reports `470000`

## Best-Supported Message Meanings From Test 9

### `4a000aff00b4000000002710`

- Round configuration packet
- `0x00b4 = 180` seconds, which matches the documented 3-minute rounds

### `58`

- Round arm/start command
- Sent once per connected blaster after startup/config is complete

### `47 [hi] [lo]`

- End-of-round aggregate counter
- In Test 9, the value matches the documented shot counts exactly: `30` and `10`
- This is much stronger evidence than the older “maybe cumulative shots” wording
- Test 8 shows the same message family in the same round-close phase for the larger multiplayer mode

### `54 [stats...]`

- End-of-round stat reply
- In Test 9 the middle bytes line up with the documented hit / kill totals:
  - `54000a0203` → `10` hits, `2` kills
  - `5400070105` → `7` hits, `1` kill
- Final byte appears to echo the queried slot/index (`03`, `05`)

### `51`

- Do **not** treat it as gameplay polling in this document
- The protocol definition already marks it as likely battery/status
- It is not part of the observed Test 9 command/notification stream used for this analysis

## Revised Confidence

| Field | Confidence | Why |
| ----- | ---------- | --- |
| Test 9 is multiplayer | **VERY STRONG** | Matches both [test_9.md](test_9.md) and the two-blaster capture |
| `4a ... 00b4 ...` = 3-minute config | **VERY STRONG** | Matches documented 3-minute rounds |
| `58` = round start/arm | **STRONG** | Appears once per blaster after setup |
| `47` = shots fired in completed round | **VERY STRONG** | `0x001e = 30`, `0x000a = 10`, exact match to handwritten notes |
| `54` contains hit / kill totals | **VERY STRONG** | `10/2` and `7/1` match the notes exactly |
| `51` is gameplay polling in Test 9 | **NOT SUPPORTED** | No `51` packets are present in the extracted Test 9 control stream |
| `47` happens strictly after `42` | **NOT SUPPORTED** | Test 8 and Test 9 both show interleaving during round close |

## Conclusion

Test 9 is best understood as a **two-blaster multiplayer capture with two completed 3-minute rounds**. The strongest protocol evidence in this test is not `51`; it is the tight correlation between:

- handwritten round results in [test_9.md](test_9.md)
- `47` values (`30`, `10`) for shots fired
- `54` values (`10/2`, `7/1`) for hits and kills

That makes Test 9 one of the cleanest captures so far for end-of-round stat semantics in multiplayer mode.
