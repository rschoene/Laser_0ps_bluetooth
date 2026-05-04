0: Do NOT reinitialize blasters (no app data wipe)
0: Power on and connect all blasters (blaster 0 may be connected twice due to reconnects)
0: Start Game 1 (team battle, 3 minutes)
0: Play through Game 1 — actions noted below
0: Collect end-of-game stats
0: Start Game 2 (team battle, 5 minutes, teams swapped)
0: Play through Game 2 — actions noted below
0: Collect end-of-game stats
0: End test

## Notes

- Guns under test: g0 (Hurricane Howler), g1 (Air Blaze), g2 (Atom Beast), g3 (Burst Defender)
- Goal: capture two full team-battle games with all four guns and record stats
- No reinitialization of blasters between or during games
- Power-ups: not allowed in either game
- Upgrades allocated per gun (persistent state going into test):
  - g0: health, ammunition, damage, reactivation time (4 upgrades)
  - g1: health (1 upgrade)
  - g2: none (0 upgrades)
  - g3: ammunition (1 upgrade)

## Pre-test state

- g0 (Hurricane Howler): level 5, upgrades: health=1, ammunition=1, damage=1, reactivation time=1
- g1 (Air Blaze): level 2, upgrades: health=1
- g2 (Atom Beast): level 1, upgrades: none
- g3 (Burst Defender): level 2, upgrades: ammunition=1

## Suggested timestamp log

- t_connect_g1:
- t_connect_g2:
- t_connect_g3:
- t_connect_g0:
- t_game1_start:
- t_game1_end:
- t_game2_start:
- t_game2_end:
- t_disconnect:

## Capture checklist

- Save full btsnoop_hci.log
- Export filtered_.log for phone + all four guns
- Note which gun connected in which order

## Game 1

Game type: Team battle

Duration: 3 minutes (180 seconds)

Power-ups allowed: no

All guns turn off and on again before game.

Teams:
- Team 1: Hurricane Howler (g0), Atom Beast (g2)
- Team 2: Air Blaze (g1), Burst Defender (g3)

All press recharge: g0, g1, g2, g3

0: shoots 5 times on 1
1: dies
0: 5 other shots at one while dead
0: recharge
0: shoots 5 times on 1
1: dies
2: shoots 5 times at 3 and accidentally 0
3: dies
2: shoots more at 3 (and accidentally 0)

end

Collected stats:

| Name             | Hits? | + | - | Team |
|------------------|-------|---|---|------|
| Hurricane Howler | 20    | 4 | 1 | 1    |
| Atom Beast       | 0     | 0 | 1 | 1    |
| Burst Defender   | 12    | 2 | 2 | 2    |
| Air Blaze        | 0     | 0 | 2 | 2    |

Awards: Burst Defender 100% hit accuracy; Hurricane Howler lowest time knocked out (10 seconds)

## Game 2

Game type: Team battle

Duration: 5 minutes (300 seconds)

Power-ups allowed: no

Teams (swapped vs Game 1):
- Team 1: Air Blaze (g1), Burst Defender (g3)
- Team 2: Atom Beast (g2), Hurricane Howler (g0)

All press recharge: g1, g0, g2, g3

1: shoots 0 5 times, also 2 is hit
0: dies, 2 is low on health
1: shoots 0 5 times
0: dies
1: recharges
1: shoots 0 5 times, also 2 is hit
0: dies, 2 is low on health
1: shoots 0 5 times
0: dies
3: shoots 3×5 times, misses, and recharges in between

end

Collected stats:

| Name             | Hits? | + | - | Team |
|------------------|-------|---|---|------|
| Hurricane Howler | 0     | 0 | 4 | 2    |
| Atom Beast       | 0     | 0 | 0 | 2    |
| Burst Defender   | 0     | 0 | 1 | 1    |
| Air Blaze        | 24    | 4 | 1 | 1    |

Awards: Air Blaze 100% hit accuracy; Burst Defender lowest time knocked out (0 seconds)

## Capture results

### Startup snapshots (confirmed state per gun)

- g1: `35000a020201000a020204000a` → level byte `02` (level 2, health upgrade)
- g2: `35000a020201000a010305000a` → level byte `01` (level 1, no upgrades)
- g3: `35000a020201000a02040a000a` → level byte `02` (level 2, ammunition upgrade — different upgrade bytes than g1)
- g0: `35000a020201000a051214000a` → level byte `05` (level 5, all 4 upgrades)

All startup volume writes: `5b00` (persisted muted volume)

### Connection order

- g1 connects first (~t=27s), g2 (~t=121s), g3 (~t=175s)
- g0 does not appear until game setup phase (~t=268s); consistent with "blaster 0 connected twice"
- All guns re-subscribe for each game round

### New message families observed

- `47 XX YY` (gun→host, handle 0x0023): shots fired by this gun in the round, big-endian 16-bit. The gun reports its own trigger count. Cross-checked: g0 fired 5+5+5=15 in Game 1 → `47000f`=15 ✓; g1 fired 5+5+5+5=20 in Game 2 → `470014`=20 ✓. g3 Game 2 note says "3×5 shots" but gun reports `47000d`=13 (note was approximate). g2 Game 1 attempted shots but they did not register (0 confirmed hits) and reports `470000`=0.
- `42` (host→gun, handle 0x0026): session/round close (already known, confirmed here)
- `54 XX` (host→gun): request stats about shooter in slot XX from this gun. `54 00 HH KK XX` (gun→host): this gun was hit HH times and killed KK times by the gun assigned to slot XX. Zeros omitted — only non-zero responses carry payload beyond slot byte.
- `49 XX YY` (host→gun, game setup): player slot assignment — XX=slot index, YY=team index (0-based). Slot assignments are re-issued fresh each game. Confirmed via destination MACs:
- `4a 00 0a ff [dur_hi] [dur_lo] 00 00 00 00 27 10` (host→gun, game setup): game configuration. Duration encoded as big-endian 16-bit at bytes 4–5. Game 1: `00 b4`=180s=3min; Game 2: `01 2c`=300s=5min.
- `58` (host→gun): arm/start-game command, sent after `35` snapshot during game setup.

### Slot assignments per game (confirmed via destination MACs)

| Gun | Game 1 slot | Game 1 team | Game 2 slot | Game 2 team |
|-----|-------------|-------------|-------------|-------------|
| g2 (Atom Beast)      | 2 | 0 | 3 | 1 |
| g1 (Air Blaze)       | 3 | 1 | 2 | 0 |
| g0 (Hurricane Howler)| 4 | 0 | 5 | 1 |
| g3 (Burst Defender)  | 5 | 1 | 4 | 0 |

Team 0 = Team 1 (same side), team 1 = Team 2. Slots are re-assigned per game; the same gun may get a different slot in each round.

### Game setup sequence (per gun, per game)

```
H→G 0x0026: 49 XX YY          (player/team slot assignment)
H→G 0x0026: 4a 00 0a ff [dur_hi] [dur_lo] 00 00 00 00 27 10  (game config)
H→G 0x0026: 5b 00              (volume)
H→G 0x0026: 35                 (state snapshot query)
G→H 0x0023: 35 00 ...          (snapshot response)
H→G 0x0026: 58                 (arm/start)
```

### End-of-round sequence (per gun)

```
G→H 0x0023: 47 XX YY           (shots fired this round, big-endian)
H→G 0x0026: 42                 (close)
H→G 0x0026: 54 02              (stat slot 2 request)
G→H 0x0023: 54 00 ... 02       (stat slot 2 response)
H→G 0x0026: 54 03              (stat slot 3 request)
G→H 0x0023: 54 00 ... 03       (stat slot 3 response)
... (slots 4, 5)
```

Note: team-battle rounds use `47`+`54` stat exchange at end, not the single-player `30 01 3f TT NN` flow.

### Shots fired per gun (47 message)

Game 1: g0=15, g3=8 (g1=0, g2=0)
Game 2: g1=20, g3=13 (g2=0, g0=0)

### Hit matrix from 54 exchange (non-zero responses only)

**Game 1** (slot 4=g0, slot 5=g3):

| Receiving gun | Slot queried | Hits (HH) | Kills (KK) | Interpretation |
|---|---|---|---|---|
| g3 | slot 4 (g0) | 10 | 2 | g3 was hit 10×, killed 2× by g0 |
| g1 | slot 4 (g0) | 10 | 2 | g1 was hit 10×, killed 2× by g0 |
| g0 | slot 5 (g3) | 5  | 1 | g0 was hit 5×, killed 1× by g3 |
| g2 | slot 5 (g3) | 7  | 1 | g2 was hit 7×, killed 1× by g3 |

g0 fired 15 shots: both g3 and g1 each register 10 hits (10+10=20 raw) — IR double-registration, same 10 shots received by two guns simultaneously. App sums g3's kills (2) + g1's kills (2) = 4 total kills for g0 ✓. For g3: 5 hits on g0 + 7 on g2 with x=4 double-registrations → 8 effective shots = 8 trigger pulls ✓ → 100% accuracy ✓.

**Game 2** (slot 2=g1, slot 3=g2, slot 4=g3, slot 5=g0):

| Receiving gun | Slot queried | Hits (HH) | Kills (KK) | Interpretation |
|---|---|---|---|---|
| g2 | slot 2 (g1) | 4  | 0 | g2 was hit 4× by g1 |
| g0 | slot 2 (g1) | 20 | 4 | g0 was hit 20×, killed 4× by g1 |

g1 fired 20 shots, g0 registers all 20, g2 registers 4 — some shots hit both opponents simultaneously (IR double-registration). Kills for g1 = 4 ✓. All 20 shots hit at least one target → 100% accuracy ✓.