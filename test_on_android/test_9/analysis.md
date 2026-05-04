# Test 9: Single-Player AR Duel - Protocol Analysis

## Test Overview
- **Scenario**: Single-player AR mode with 2 guns (stat-query validation test)
- **Guns**: g0, g1 (gun_0, gun_1 in traces)
- **Protocol Focus**: Stat exchange and cumulative shot recording
- **Key Difference from Test 8**: Includes `47` messages during gameplay

## Important Discovery: Message 47 in Game Context

Test 9 reveals that message `47` **IS sent during gameplay**, but only in certain contexts:
- **NOT** during continuous multiplayer action
- **Appears** in stat-query phases or at game transitions
- Contains cumulative shot/hit information

## Game Timeline

### Game 1 Setup (t=7s)

**Slot Assignment**:
- Host → Gun 0: `490200` (Slot 2)
- Host → Gun 1: `490301` (Slot 3)

**Game Configuration**:
- Host → Both: `4a000aff00b4000000002710`
  - Duration: `0x00b4` = 180 seconds (3 minutes) ✓
  - Same encoding as Test 8

**Game Start**:
- Host → Gun 0: `58` (arm/start)
- Host → Gun 1: `58`

### Game 1 Active Phase (t=7-213s)

**Initial State**:
- Gun 0 state snapshot: `35000a020201000a020204000a` (level 2, upgrades)
- Gun 1 state snapshot: `35000a020201000a051214000a` (level 5, upgrades)

**Status Polling**:
- Periodic `51` host queries
- Gun responses with `5102XX` status words
- **Pattern**: Every ~30-50s

### Game 1 End & Stat Exchange (t=213-214s)

**Close Session**:
- Host → Guns: `42` (session close)

**Message 47 Appearance** (CRITICAL):
- Gun 1: `47001e` → **0x1e = 30 decimal** (possibly cumulative shots in this game?)
- Gun 0: `470000` → **0 shots/hits**

**Stat Slot Query**:
- Host → Gun 0: `5402` (query slot 2)
- Gun 1 response: `5400000002` 
  - Format: `54 [index] [hits] [kills] [status]`
  - Slot 2: 0 hits, 0 kills, status=0x02

- Host → Gun 0: `5403` (query slot 3)
- Gun 0 response: `54000a0203`
  - Slot 3: 0xa=10 hits, 0x02=2 kills, status=0x03

**Interpretation**:
- Slot 2 (Gun 1): 0 hits, 0 kills
- Slot 3 (Gun 0): 10 hits, 2 kills
- Message `47001e` from Gun 1 might indicate: 30 shots fired (not hits)

### Game 2 Setup (t=409s)

**Slot Assignment** (3rd game):
- Host → Gun 0: `490400` (Slot 4)
- Host → Gun 1: `490501` (Slot 5)

**Game Configuration**:
- Same: `4a000aff00b4000000002710` (3 min)

**Game Start**:
- Host → Both: `58`

### Game 2 Active Phase (t=409-607s)

Same polling pattern as Game 1

### Game 2 End & Stat Exchange (t=607s)

**Message 47 Appearance** (Again!):
- Gun 1: `47000a` → **0x0a = 10 decimal** (shots fired this game?)
- Gun 0: `470000` → 0

**Stat Responses**:
- Host → Gun 0: `5404` (query slot 4)
- Gun 1 response: `5400000004`
  - Slot 4: 0 hits, 0 kills, status=0x04

- Host → Gun 0: `5405` (query slot 5)
- Gun 0 response: `5400070105`
  - Slot 5: 0x07=7 hits, 0x01=1 kill, status=0x05

## Protocol Message Analysis

### Message 47: Cumulative Shot Counter

**Hypothesis** (based on Test 9 evidence):
- Format: `47 [high_byte] [low_byte]`
- Content: **Cumulative shots fired during THIS game session**
- When sent: **At end-of-game stat exchange**, along with `42` close and `54` slot queries

**Observations**:
- Game 1: Gun 1 sent `47001e` (30 shots), Gun 0 sent `470000` (0 shots)
- Game 2: Gun 1 sent `47000a` (10 shots), Gun 0 sent `470000` (0 shots)
- Gun 1 always had shots fired, Gun 0 always zero → consistent per-player pattern

**Distinction from `54` responses**:
- `47`: Shots fired (count)
- `54`: Hits and kills (effectiveness)
  - Example: Gun 1 fired 30 shots → 0 hits (missed all)
  - Example: Gun 0 fired 0 shots → 7 hits, 1 kill (from previous rounds?)

**Mystery**: How did Gun 0 get 7 hits if it fired 0 shots in this game? 
- Possible: Carryover from earlier incomplete game?
- Or: Test data corruption (stat persistence issue)?

## Confidence Ratings

| Field | Confidence | Notes |
|-------|-----------|-------|
| Slot assignment (`49 XX YY`) | **STRONG** | Consistent across games |
| Game duration (`4a ...00b4...`) | **STRONG** | 3min verified in 2 games |
| Session close (`42`) | **STRONG** | Marks end-of-game |
| Status polling (`51`) | **STRONG** | Continuous during play |
| Message `47` = shot count | **MODERATE** | Pattern matches (0x1e=30, 0x0a=10), but needs validation |
| Message `47` timing | **MODERATE** | Sent at game end with `42` and `54` |
| Slot stat format (`54`) | **STRONG** | Clear hits/kills/status fields |
| NO trigger events during active play | **STRONG** | Consistent with Test 8 |

## Key Insight: Two Message Categories

**During Active Gameplay**:
- Status polling only (`51`, `5102XX`)
- No individual trigger/reload events
- No cumulative shot counters

**At Game End** (with `42` close):
- Message `47`: Cumulative shots fired
- Slot queries (`5402`, `5403`, ...): Stat matrix exchange
- Slot responses (`5400XX...`): Hits/kills per slot

**Implication**: Game stats are aggregated and sent only at session end, not during play.

## Comparison: Test 8 vs Test 9

| Aspect | Test 8 | Test 9 |
|--------|--------|--------|
| Game mode | 4v4 multiplayer | Single-player AR |
| Guns | 4 | 2 |
| Message `47` | Not captured | Captured at game end |
| Message `54` | Captured | Captured |
| Duration | 3 min (0x00b4) | 3 min (0x00b4) |
| Status polling | Yes | Yes |
| Trigger events | None (as expected) | None (as expected) |

**Hypothesis**: Test 8 may have terminated before stat exchange completed, or stat exchange is optional for multiplayer.

## Next Steps

1. **Validate `47` = shot count**: Check if 0x1e=30 and 0x0a=10 represent actual shots fired
2. **Investigate stat persistence**: Why does Gun 0 show 7 hits after firing 0 shots?
3. **Test 10**: Controlled single-player to validate shot/hit/kill semantics
4. **Complete Test 8 analysis**: Check if `47` messages exist later in the capture
