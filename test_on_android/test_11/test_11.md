no reinitialization
connect g1: air blaze
connect g0: Hurricane Howler
connect g4: Shadow Blaze

g1 stats (alpha point):
- health: 15 (10 + 5 from upgrade health level 1)
- damage : 2 (2 base)
- shots per recharge: 10 (10 base)
- reload time: 0.5 s (0.5 base)
- respawn time: 10 s (10 base)
- 0 powerups

g0 stats (alpha point):
- health: 15 (10 base + 5 from upgrade health level 1)
- damage : 3 (2 base) + 1 from upgrade damage)
- shots per recharge: 13 (10 base + 3 from upgrade recharge)
- reload time: 0.5 s (base)
- respawn time: 9 s (10 base - 1 from upgrade respawn time)
- 3 powerups

g4 stats (delta burst):
- health: 10 (10 base)
- damage : 2 (1+1 from upgrade damage level 1)
- shots per recharge: 18 (18 base)
- reload time: 0.75 s (0.75 base)
- respawn time: 10 s (10 s base)
- 0 powerups

app: 5 minute game all vs all

app: start

g0: confirm start via reload
g1: confirm start via reload
g4: disconnects

g0: shoots
- hits g1 5 times
- hits nothing 20 times

g1: dies 1 time

app: game ends, collect data

| Name             | Hits? | + | - |
|------------------|-------|---|---|
| Hurricane Howler | 5     | 1 | 0 |
| Air Blaze        |  0    | 0 | 1 |

app: g0 has 20.83% hit rate

app: Unlocked Power-Ups at some guns, probably health


------------------------------------------------------------

app: connect g4
app: 5 minute game all vs all

app: start

g4: confirm start via reload
g0: confirm start via reload
g1: confirm start via reload

g0: shoots 36 times, hits 35 times, kills g4 7 times
g1: shoots 5 times, hits 5 times, kills g4 1 time
g4: shoots 0 times, dies 8 times 

| Name             | Hits? | + | - |
|------------------|-------|---|---|
| Hurricane Howler | 35    | 7 | 0 |
| Air Blaze        |  5    | 1 | 0 |
| Shadow Blaze     |  0    | 0 | 8 |

## Protocol confirmation and upgrade extension

### Confirmed previous multiplayer findings in this capture

- Per-gun all-vs-all start sequence is unchanged: `49` -> `4a` -> `5b00` -> `35` -> `35...` -> `58`.
	- Example (round 1, g0): frames 812, 814, 817, 819, 821, 823.
	- Example (round 2, g0): frames 2384, 2391, 2397, 2401, 2404, 2405.
- End-of-round stats still use `47` (shots) and `54` (hits/kills by shooter slot).
	- Round 1 shots: `470018` (g0), `470002` (g1).
	- Round 2 shots: `470024` (g0), `470005` (g1), `470000` (g4).

### Upgrade state is still reported in all-vs-all

- Startup snapshots (`35...`) still carry persistent per-gun state and match prior tests:
	- g0: `35000a020201000a051214000a` (frame 821 / 2404 / 3650)
	- g1: `35000a020201000a020204000a` (frame 998 / 2382 / 3595)
	- g4: `350012010200010a022704000a` (frame 1187 / 2396 / 3688)
- These values are stable across reconnects and round starts, so there is no sign of a reset to base profile when starting all-vs-all.

### Are upgrades disabled during game initialization?

- In the ATT game/setup flow for this test, no `36...` config writes were observed (`count36 = 0` in extracted handle 0x0026/0x0023 data).
- So for this capture, the app does not appear to push a downgrade/base config at all-vs-all initialization.

### Do upgrades count in all-vs-all outcomes?

- Round 1 alone is ambiguous:
	- `5400050102` confirms 5 hits and 1 kill for one shooter.
	- This can fit both models:
	  - upgraded model: 15 HP target with 3 damage/hit
	  - base model: 10 HP target with 2 damage/hit
- Round 2 is the stronger discriminator:
	- g4 reports `5400230704` (35 hits, 7 kills) and `5400050102` (5 hits, 1 kill).
	- Both shooters show exactly 5 hits/kill against the same target in the same round.
	- If g4 has 10 HP (as noted), this implies effective damage 2/hit for both shooters in this mode.
	- If g4 had 15 HP, 5 hits/kill would imply 3 damage/hit for both shooters, which conflicts with g1 having no damage upgrade.
- Current best interpretation from Test 11:
	- Upgrade state is still reported at startup (`35...`), but all-vs-all combat damage appears to be normalized/base-like (effective 2 damage/hit here).
	- So Test 11 does not support "g0 damage upgrade is active in all-vs-all" for round scoring.

### Power-ups note

- This capture shows no clear dedicated power-up activation command family during match start/play.
- The post-match "Unlocked Power-Ups" UI event is likely progression/state update, not evidence of an in-round protocol toggle in this log.

### Confidence and limits

- Strong confidence: upgrades are still reported in startup snapshots and are not explicitly disabled by init config writes in this test.
- Moderate confidence: at least damage seems base/normalized in all-vs-all scoring for this capture (5 hits/kill pattern in round 2).
- Not proven here: direct in-round protocol toggles for power-ups, and isolated effects of ammo/reload upgrades in all-vs-all.
