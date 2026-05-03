0: Do NOT delete app data
0: Ensure gun 0 is already level 4 in app before connecting
0: Verify upgrades are exactly: health=1, munition capacity=1, damage=1, reload speed=1
0: Power on and connect only gun 0
0: Enter single-player AR mode
0: Start a short single-player game
0: Do not shoot, do not reload, do not change volume, no manual interaction
0: changes in ui: 13 munition, 15 life
0: Let session run briefly (10-20s)
0: get killed by all, 941/1525 xp needed for level 5
0: End test

## Notes

- Gun under test: g0
- Goal: isolate protocol differences caused by persistent state changes only
- Persistent state under test:
  - level = 4
  - upgrades: health=1, munition=1, damage=1, reload=1
- No gameplay interactions during the run

## Pre-test state

- Confirmed level in app: 4
- Upgrade points allocated:
  - health: 1
  - munition capacity: 1
  - damage: 1
  - reload speed: 1

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

## Expected comparison targets vs Tests 2-5

- startup snapshot payload: 35 00 0a 02 02 01 00 0a LL NN MM 00 0a
- config write payload(s): 36 00 0a 02 02 [01|03] 00 0a LL NN MM 00 [0a|04]
- potential changed parameters in control writes (44/49/4a/41/3b/39)
- confirm no XP transfer field appears

## Capture results

- Startup/report write-read pair:
  - host -> gun: `35`
  - gun -> host: `35000a020201000a041214000a`
- Level byte `LL` is now `04` (was `03` in Tests 1-5).
- Startup volume write is now `5b00` (matches persisted volume=0), not `5b1f`.
- Config write observed:
  - `36000d030203000f0412140004`
  - vs previous level-3 baseline `36000a020203000a0312140004`
  - changed bytes: `0a->0d`, `02->03`, `0a->0f`, `03->04`
- No interaction event families appeared (as intended):
  - `49`: 0
  - `52`: 0
  - `310a`: 0
  - `3202xx/320axx`: 0
- End-of-round/stat sequence changed range:
  - Test 6: `30013f010e` down to `30013f0100`
  - Earlier baseline: `30013f0109` down to `30013f0100`

Interpretation:
- `35...` is a state report from gun, `36...` is a state write from host.
- Persistent progression state (level/upgrades) now changes both report and write payload bytes.
- Volume set command `5bxx` uses persisted current volume at startup.
