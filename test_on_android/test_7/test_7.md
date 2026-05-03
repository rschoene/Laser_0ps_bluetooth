0: Do NOT delete app data
0: Level up gun 0 to level 5 before capture start (required two single-player games)
0: Verify upgrades are exactly: health=1, ammunition=1, damage=1, reactivation time=1
0: Power on and connect only gun 0
0: Enter single-player AR mode
0: Start a short single-player game
0: Do not shoot, do not reload, do not change volume, no manual interaction
0: Let session run briefly (10-20s)
0: End game from host/app
0: End test

## Notes

- Gun under test: g0
- Goal: isolate byte-level protocol deltas from Test 6 to Test 7
- Persistent state under test:
  - level = 5
  - upgrades: health=1, ammunition=1, damage=1, reactivation time=1
- Level-up path used before this capture: two single-player games to reach level 5
- Delta vs Test 6:
  - the 4th upgrade changed from reload speed to reactivation time

## Pre-test state

- Confirmed level in app: 5
- Upgrade points allocated:
  - health: 1
  - ammunition: 1
  - damage: 1
  - reactivation time: 1

## Suggested timestamp log

- t_connect:
- t_startup_snapshot:
- t_game_start:
- t_game_end:
- t_disconnect:

## Capture checklist

- Save full btsnoop_hci.log
- Export filtered_.log for phone + gun 0
- Keep screenshot/note of level and upgrade screen before test

## Expected comparison targets vs Tests 6 and 5

- startup snapshot payload: 35 00 0a 02 02 01 00 0a LL NN MM 00 0a
- config write payload(s): 36 ...
- control writes (44/49/4a/41/3b/39)
- end/stat range: 30013f01xx upper bound
- confirm no explicit XP transfer field appears

## Capture results

- Capture contained two phases:
  - Phase A (start): level-4 state still active
  - Phase B (late in log): level-5 sync/state writes appear

### Phase A (early, around t=180s)

- Startup report from gun:
  - `35000a020201000a041214000a` (level byte still `04`)
- Initial state write from host:
  - `36000d030203000f0412140003`
- Startup volume write:
  - `5b00` (persisted muted volume)

### Phase B (late, around t=1876s+)

- New level-5 state writes appear:
  - `36000a020201000a051214000a`
  - `36000a020203000a0512140004`
  - `36000d030203000f0512140003`

Interpretation: level transition to 5 is represented by `...051214...` inside `36...` writes.

### Message-family changes vs Test 6

- Gameplay/reload families changed:
  - old (Tests 5/6 era): `3202xx` / `320axx`, `310a`, `370a0100`
  - Test 7 observed: `3203xx` / `320exx`, `310d`, `370e0100`
- Counts in this capture:
  - `49`: 1892
  - `52`: 147
  - `310d`: 147
  - `310a`: 0
  - `3203/320e`: 1374
  - `3202/320a`: 0

### End/stat sequence

- Observed `30013f01xx` suffix set: `00 04 05 06 07 0e`
- Note: this run contains multiple rounds/phases, so not every intermediate suffix is present in the unique-set view.
