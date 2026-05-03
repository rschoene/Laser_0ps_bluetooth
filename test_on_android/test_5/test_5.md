0: Do NOT delete app data (preserve XP / level state from previous tests)
0: Power on gun 0 only
0: Connect gun 0
0: Lower volume to 0 before starting the game
0: Start single-player AR game
0: Play until a level-up occurs
0: Note exact timestamp of level-up UI event
0: End game
0: End test

## Notes

- Gun under test: g0
- App data: preserved (carry over XP and level from previous sessions)
- Volume: set to 0 before gameplay starts
- Goal: capture the BLE traffic that occurs when the app writes a new level to the gun after a level-up

## Pre-test state

- Gun 0 level before test:
- Total XP before test: (was 328 after test 3/4)
- XP needed for next level-up:

## Suggested timestamp log

- t_connect:
- t_volume_0:
- t_game_start:
- t_level_up:
- t_game_end:

## Capture results

(to be filled after capture)
