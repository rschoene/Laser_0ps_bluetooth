# Definition of tests

## How to collect the logs
- Disable bluetooth
- (Extra options per test)
- Go to Settings -> Systems -> Developer Options -> Enable Bluetooth HCI snoop stack protocol
- Disable bluetooth
- Enable Bluetooth
- Start app
- (Execute test)
- (Extra options after test, defined in test)
- Disable Bluetooth
- Go to Settings -> Systems -> Developer Options -> Create Error Log -> Full Error Log
- Extract Data from zip: /FS/data/misc/bluetooth/logs/btsnoop_hci.log
- Open the log in wireshark
- filter for devices
- export filtered log


## Test 1: Basic Connection and Initialization

### Objective
Verify that all four guns can be connected simultaneously and that the app properly handles initial connections and gun identification.

### Preparations
- Delete App data
- Ensure all four guns are powered on and in pairing mode
- Clear any previous Bluetooth pairings on the test device

### Test execution
- Connect four guns (g0 ... g3) to a smartphone
- Set the first name for each gun gi (i in {0,1,2,3}) to i and the last name to `1<<i+1` (i.e., g0: first="0", last="2"; g1: first="1", last="4"; g2: first="2", last="8"; g3: first="3", last="16")
- Wait for all guns to show as connected in the app
- Navigate through the app interface to verify all four guns are visible and accessible
- Record the connection time for each gun

### Expected results
- All four guns connect successfully
- Gun names are correctly displayed in the app
- No connection drops during initialization
- App responds normally to all UI interactions

### Post-test
- Export logs from Wireshark
- Analyze connection sequence and message patterns
- Verify HCI events match expected Bluetooth protocol


## Test 2: Single-Player AR Game With Gun 0

### Objective
Observe Bluetooth traffic for a minimal single-player AR session with only gun 0 connected, focusing on trigger events, reload-related events, sound-related traffic, and any level progression updates.

### Preparations
- Delete app data
- Ensure only gun 0 is powered on and available for pairing
- Clear previous Bluetooth pairings if needed
- Start with gun 0 in a known default state

### Test setup
- Connect only gun 0 to the smartphone
- Do not configure more than required to enter the game
- Skip optional gun setup steps where possible
- Enter the single-player augmented reality mode that uses the smartphone as the camera view

### Test execution
- Start a new single-player game with gun 0
- Move the smartphone to track enemies in augmented reality
- Fire repeatedly at enemies
- Perform at least one deliberate reload action if the UI or gun requires it
- Continue until at least one level increase or progression event is visible in the app
- Record any visible sound changes or sound effects that appear tied to gameplay events

### Data to record during the test
- Timestamp when gun 0 connects
- Timestamp when the AR game starts
- Number of trigger pulls / shots
- Whether reload occurs and when
- Whether the app shows level increase and when
- Whether any sound change is observed and when
- Any connection drop or UI anomaly

### Expected results
- Gun 0 connects successfully and remains connected during the session
- Trigger traffic appears on the gun-to-host event path
- Additional traffic appears around reload, progression, or sound-related actions
- If level progression occurs, at least one payload field should change in a way that can be correlated with the new state
- No unnecessary setup traffic from additional guns is present

### Post-test
- Export logs from Wireshark
- Filter to gun 0 only
- Compare the capture to Test 1
- Identify:
  - trigger event traffic
  - reload-related traffic
  - any new traffic introduced by the AR gameplay loop
  - any level or progression-related payload changes
  - any traffic that appears correlated with sound playback or sound state


## Test 3: Single-Player AR No-Reload + Volume Sweep (Gun 0)

### Objective
Repeat the Test 2 single-player AR flow with gun 0 while isolating two effects:
- shooting traffic without any reload action
- gun volume control traffic while stepping volume from max (10) down to min (0)

### Preparations
- Delete app data
- Ensure only gun 0 is powered on and available for pairing
- Clear previous Bluetooth pairings if needed
- Start with gun 0 in a known default state

### Test setup
- Connect only gun 0 to the smartphone
- Skip optional setup where possible
- Enter single-player augmented reality mode

### Test execution
- Start a single-player AR game with gun 0
- Perform shooting only (do not manually reload)
- Continue shooting long enough to produce a stable stream of trigger-related traffic
- End the game/session
- After gameplay, change gun volume in explicit steps:
  - 10 -> 9 -> 8 -> 7 -> 6 -> 5 -> 4 -> 3 -> 2 -> 1 -> 0
- Pause briefly between each step so message boundaries can be separated in logs

### Data to record during the test
- Timestamp when gun 0 connects
- Timestamp when AR game starts
- Number of shots / trigger pulls
- Confirmation that no manual reload was performed
- Timestamps for each volume step change (10..0)
- Any sound behavior observed at each volume level
- Any connection drop or UI anomaly

### Expected results
- Gun 0 remains connected for the full session
- Trigger event traffic is present
- Reload-specific traffic should be reduced or absent compared with Test 2
- Distinct traffic should appear for each volume change step
- Message families related to volume control can be separated from gameplay traffic

### Post-test
- Export logs from Wireshark
- Filter to gun 0 only
- Compare Test 3 against Test 2 with focus on:
  - trigger traffic similarities
  - missing/reduced reload-like message families
  - message sequences that correlate with each volume step (10..0)
- Build a candidate mapping table: volume level -> payload delta


## Test 4: Volume-Only Sweep (Gun 0, No Gameplay)

### Objective
Isolate volume control traffic on gun 0 without gameplay noise by running only volume changes in three phases: down, up, down.

### Preparations
- Delete app data
- Ensure only gun 0 is powered on and available for pairing
- Clear previous Bluetooth pairings if needed
- Keep gameplay disabled for this test

### Test setup
- Connect only gun 0 to the smartphone
- Skip optional setup where possible
- Do not start a single-player game
- Wait until startup traffic completes before changing volume

### Test execution
- Perform volume sweep 1: 10 -> 9 -> 8 -> 7 -> 6 -> 5 -> 4 -> 3 -> 2 -> 1 -> 0
- Perform volume sweep 2: 0 -> 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10
- Perform volume sweep 3: 10 -> 9 -> 8 -> 7 -> 6 -> 5 -> 4 -> 3 -> 2 -> 1 -> 0
- Pause briefly between each step to separate packets clearly
- Do not shoot and do not manually reload during this test

### Data to record during the test
- Timestamp when gun 0 connects
- Timestamp when startup exchange ends
- Timestamp for every volume step change
- Visible app volume value per step
- Audible change observations per step
- Any connection drop or UI anomaly

### Expected results
- Volume-change traffic appears in a clean, repeatable pattern
- The same payload family repeats for equivalent volume levels in each sweep
- Startup `5b1f` can be separated from manual volume writes by timing and value pattern
- Minimal or no trigger/reload/gameplay events are present

### Post-test
- Export logs from Wireshark
- Filter to gun 0 only
- Build exact mapping table: UI volume level -> payload value
- Compare descending and ascending sweeps for symmetry
- Verify whether `5b1f` is outside the stepwise mapping (startup-only) or part of max-volume mapping


## Test 5: Level-Up Capture (Gun 0, Preserved App Data)

### Objective
Capture the BLE traffic that occurs when a level-up event happens during gameplay, specifically to determine whether the new level is written to the gun over BLE and in which message.

### Background
- Level is stored on the gun: the startup snapshot (`35...`) reports `LL` (level byte), and the `36` config write contains the same byte.
- XP and gained XP are never transmitted over BLE (confirmed in tests 2–4).
- After tests 1–4, gun 0 is at level 3. A level-up would result in a new `36` write with `LL = 04` (or next level index).

### Preparations
- Do NOT delete app data (keep accumulated XP and level state from previous tests)
- Ensure only gun 0 is powered on
- Note the current level and total XP shown in the app before connecting

### Test setup
- Connect only gun 0
- Lower volume to 0 before starting the game (to suppress gun sound during the test and isolate any volume-related traffic)
- Enter single-player AR mode

### Test execution
- Start a single-player AR game
- Play actively to gain XP
- At the moment a level-up appears in the app UI, record the exact timestamp
- Continue briefly after the level-up to capture any follow-up traffic
- End the game normally

### Data to record during the test
- Gun 0 level before test (from app)
- Total XP before test
- XP needed for next level-up
- Timestamp of level-up UI event
- Any visible change in the app at level-up (animation, sound, popup)
- Any connection drop or anomaly

### Expected results
- A new `36` config write on handle `0x0026` appears around the level-up timestamp with an incremented `LL` byte
- Alternatively, the startup snapshot `35...` on the next reconnect reflects the new level
- The XP or gained XP value itself does not appear in any BLE payload (consistent with previous tests)

### Post-test
- Export logs from Wireshark
- Filter to gun 0 only
- Find all `36` writes and compare to previous tests — look for changed `LL` byte
- Check whether the level write happens immediately at level-up or only on next connection
- Record which test timestamp the level-change write corresponds to


## Test 6: Level-4 + Upgrade-State Sync (Gun 0, No Interaction)

### Objective
Identify protocol differences that are caused only by persisted gun/app state after progression, using a minimal session with no gameplay interactions.

### Background
- Gun 0 is now level 4 in the app.
- Upgrades are allocated as:
  - health = 1
  - munition capacity = 1
  - damage = 1
  - reload speed = 1
- Previous tests at level 3 showed stable startup/config fields.

### Preparations
- Do NOT delete app data
- Ensure only gun 0 is powered on
- Confirm in app before test:
  - level = 4
  - upgrades = 1/1/1/1 (health/munition/damage/reload)

### Test setup
- Connect only gun 0
- Enter single-player AR mode
- Start a short game session

### Test execution
- Do not shoot
- Do not reload
- Do not change volume
- Do not interact after game start (let the session run briefly)
- End game from host/app

### Data to record during the test
- Timestamp when gun 0 connects
- Timestamp of startup snapshot reception
- Timestamp when game starts
- Timestamp when game ends
- Screenshot or note proving level/upgrades state before test
- Any connection drop or anomaly

### Expected results
- Startup `35...` and/or `36...` payloads may reflect level 4 (`LL = 04`) and possibly upgrade-related parameter deltas
- Control payloads may differ from Tests 2–5 even without gameplay interaction
- No explicit XP or gained-XP field is expected in BLE payloads

### Post-test
- Export logs from Wireshark
- Filter to gun 0 only
- Diff Test 6 against Tests 4 and 5 with focus on:
  - `35...` startup snapshot bytes
  - `36...` config write bytes
  - control writes (`44/49/4a/41/3b/39`)
- Record exact byte-level differences attributable to new level/upgrades state


## Test 7: Level-5 Sync Delta (Gun 0, No Interaction)

### Objective
Capture protocol differences after progressing from level 4 to level 5 and changing the 4th upgrade choice, while keeping gameplay interaction minimized.

### Background
- Target state before capture:
  - level = 5
  - upgrades: health=1, ammunition=1, damage=1, reactivation time=1
- Delta vs Test 6:
  - previously: health=1, munition=1, damage=1, reload speed=1
  - now: health=1, ammunition=1, damage=1, reactivation time=1

### Preparations
- Do NOT delete app data
- Ensure only gun 0 is powered on
- Reach level 5 before this capture run (in this case, two single-player games were required)
- Confirm in app before test:
  - level = 5
  - upgrades exactly match the target set above

### Test setup
- Connect only gun 0
- Enter single-player AR mode
- Start a short game session

### Test execution
- Do not shoot
- Do not reload
- Do not change volume
- Do not interact after game start (let the session run briefly)
- End game from host/app

### Data to record during the test
- Timestamp when gun 0 connects
- Timestamp of startup snapshot reception
- Timestamp when game starts
- Timestamp when game ends
- Screenshot or note proving level/upgrades state before test
- Any connection drop or anomaly

### Expected results
- Startup `35...` should report `LL = 05` if level is synchronized
- `36...` config write may show byte deltas vs Test 6 related to level and the changed 4th upgrade choice
- End/stat range (`30013f01xx`) upper bound may shift again vs Test 6
- No explicit XP or gained-XP field is expected in BLE payloads

### Post-test
- Export logs from Wireshark
- Filter to gun 0 only
- Diff Test 7 against Tests 6 and 5 with focus on:
  - startup snapshot `35...`
  - config write `36...`
  - control writes (`44/49/4a/41/3b/39`)
  - end/stat range (`30013f01xx` upper bound)
- Record exact byte-level deltas attributable to level 5 and changed upgrade selection
