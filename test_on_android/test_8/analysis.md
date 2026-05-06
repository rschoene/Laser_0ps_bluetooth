# Test 8: Four-Blaster Multiplayer Team Battle - Verified Analysis

## Verified Scope

- Scenario: four connected blasters, two multiplayer team-battle rounds
- Round 1 duration: 3 minutes (`0x00b4`)
- Round 2 duration: 5 minutes (`0x012c`)
- Cross-check basis: the raw notes in [test_8.md](test_8.md), plus the corrected Test 9 interpretation in [analysis.md](../test_9/analysis.md)

## Corrections To The Earlier Analysis

- This is **not** a 4v4 match. It is a four-blaster team battle with two teams of two.
- The two rounds are **not both 3 minutes**. Round 1 is 3 minutes; Round 2 is 5 minutes.
- `47` is part of the end-of-round stat exchange, but it does **not** occur strictly after `42`. In both Test 8 and Test 9, `47` and `42` are interleaved during the round-close sequence.
- The earlier wording `51 = gameplay polling` was too strong. Test 8 does show `51`/`5102XX`, but [protocol_definition.json](../../definition_protocol/protocol_definition.json) only supports a likely battery/status interpretation, and Test 9 does not require `51` for the round-control flow.
- The earlier gun labels were inconsistent (`Gun 4` in a four-gun test). This analysis uses g0-g3 and the anonymized device order consistently.

## Shared Multiplayer Flow Confirmed By Test 8 And Test 9

Both captures show the same multiplayer round structure:

1. Per-blaster setup:
   - `49 XX YY`
   - `4a ... [duration] ...`
   - `5b00`
   - `35`
   - `35...` response
   - `58`
2. Round-close exchange:
   - one or more `47 [count]` notifications from blasters
   - host `42` close commands
   - host `54 XX` slot queries
   - gun `5400...XX` stat replies

That common structure matters more than the exact interleaving order, which varies by blaster.

## Strong Findings From Test 8

### `49 XX YY` is a host-originated multiplayer assignment packet

Test 8 repeatedly sends `49` from host to gun during round setup, never from gun to host. Combined with the detailed slot mapping in [test_8.md](test_8.md), the best-supported interpretation is:

- byte 1: slot/index
- byte 2: team or side indicator

This directly contradicts the old `49 = trigger` interpretation.

### `4a` carries round configuration, including duration

Test 8 contains two distinct values:

- `4a000aff00b4000000002710` for Round 1 (`0x00b4 = 180s`)
- `4a000aff012c000000002710` for Round 2 (`0x012c = 300s`)

This is one of the strongest packet-level findings in the repo.

### `58` is the per-blaster arm/start command

It always appears after setup and snapshot exchange, immediately before the round begins for that blaster.

### `47` is an end-of-round aggregate shot counter

Test 8 alone suggested this strongly; Test 9 makes it much harder to dispute.

Observed Test 8 values:

- Round 1: `470008`, `47000f`, `470000`, `470000`
- Round 2: `47000d`, `470014`, `470000`, `470000`

These are consistent with the handwritten gameplay notes in [test_8.md](test_8.md), allowing for approximate human note-taking and multiplayer IR double-registration.

### `54` is the end-of-round per-slot stat response family

Test 8 is noisier than Test 9 because multiple players and overlapping IR hits make attribution harder, but the pattern is still clear:

- host sends `54 02`, `54 03`, `54 04`, `54 05`
- guns answer with `5400...02`, `5400...03`, `5400...04`, `5400...05`

Test 9 then confirms that the middle bytes in non-zero `54` replies are hit and kill totals. That means Test 8 should be read as the same structure, just with more ambiguous multiplayer interactions.

## What Test 8 Does And Does Not Prove

### Strongly supported

- multiplayer setup uses `49`, `4a`, `5b`, `35`, `58`
- end-of-round stats use `47`, `42`, `54`
- `47` is per-blaster round aggregate, not a live trigger packet
- `54` replies are keyed by queried slot/index

### Not proven by Test 8 alone

- exact semantics of every `51XXYY` state value
- exact byte naming inside `49 XX YY`
- exact per-player reconstruction of every overlapping hit in the four-blaster rounds

## Final Combined Interpretation

Using Test 8 and Test 9 together:

- Test 8 establishes the full multiplayer packet families across four blasters and two round lengths.
- Test 9 provides the cleanest correlation between packet values and handwritten results.
- Therefore the strongest shared multiplayer interpretation is: `49` = multiplayer participant assignment.
- `4a` = round configuration, including duration.
- `58` = start/arm.
- `47` = shots fired in the completed round.
- `54` = hit/kill stats for the queried slot/index.
- `51` = separate battery/status-style exchange, not needed to explain the multiplayer round flow.

This combined reading should be treated as the current best-supported multiplayer model for Tests 8 and 9.

