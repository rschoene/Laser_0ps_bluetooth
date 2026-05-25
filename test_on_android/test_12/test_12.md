# Test 12 - Multiplayer (g0 vs g1)

## Device mapping

- `HH` = `g0` = Hurricane Howler
- `AiBl` = `g1` = Air Blaze

## Scenario overview

- Mode: all-vs-all multiplayer
- Duration: 180 seconds (3 minutes) per round
- Power-ups: disabled for game setup

## Preparation / setup changes

1. Initial connection state:
	 - g0 connected, level 5
	 - g1 connected, level 2
2. Game canceled, entered blaster menu.
3. g0 changes:
	 - action: reset all upgrades
	 - status: all power-ups unlocked
	 - status: all power-up upgrades unlocked (level 1)
4. g1 changes:
	 - status: upgrade damage
	 - status: all power-ups unlocked
	 - status: no power-up upgrades unlocked

## Round 1

### Flow

- Started game (180 s, all-vs-all, no power-ups).
- g0 connected.
- g1 connected.
- Start game.
- g1 confirm.
- g0 confirm.
- g1 blinks.
- g0 blinks.
- Host volume actions during round:
	- increase volume -> ignored?
	- increase volume -> ignored?
	- increase volume to max -> ignored?
	- set volume to min -> ignored?
- End of round: device counts down from 10, then stats are collected.

### Observations

- g0: 11 shots, 10 hits, 2 kills, 1 death.
- g1: 6 shots, 5 hits, 1 kill, 2 deaths.
- g0 hit accuracy: 90.91%.
- g0 downtime: 10 seconds "dead".

### Scoreboard

| Name             | Hits | + | - | Score |
|------------------|------|---|---|-------|
| Hurricane Howler | 10   | 2 | 1 | 60    |
| Air Blaze        | 5    | 1 | 2 | 30    |

## Upgrade step

- g0 action: select upgrade "Reactivation time".

## Round 2

### Flow

- Mode: all-vs-all, 3 minutes.
- Start game.
- g1 confirm.
- g1 blinks.
- g0 blinks.
- g1 shoots and kills (not every shot was a hit).
- Sound test note: "no sound on 1".

### Observations

- g1 hit rate: 31.58%.
- g0 downtime: 10 seconds "dead".

### Scoreboard

| Name             | Hits | + | - | Score |
|------------------|------|---|---|-------|
| Air Blaze        | 12   | 2 | 0 | 62    |
| Hurricane Howler | 0    | 0 | 1 | 0     |

## Round 3 (Rematch)

### Flow and observations

- g1 shoots and kills g0.
- g0 shoots back:
	- after 3 hits, g1 health is yellow
	- after 2 more hits, health still yellow, then g1 dies
- g0 ammo state progression:
	- after 6 shots: ammo yellow
	- after 9 shots: ammo red
	- after 10 shots: empty
- g0 hit rate: 100%.
- g0 downtime: 10 seconds "dead".

### Scoreboard

| Name             | Hits | + | - | Score |
|------------------|------|---|---|-------|
| Hurricane Howler | 16   | 3 | 1 | 91    |
| Air Blaze        | 8    | 1 | 3 | 33    |

## Round 4 (Ammo-upgrade check)

### Pre-round changes

- g0 action: reset upgrades.
- g0 action: select upgrade "Munition".

### Flow and observations

- Started game (180 s, all-vs-all, no power-ups).
- g0 shoots 3 times -> g1 health yellow.
- g0 shoots 2 times -> g1 dead.
- g1 revives.
- g0 shoots 1 time -> g0 ammo yellow.
- g0 shoots 2 times -> g1 health yellow.
- g0 shoots 2 times -> g1 dead.
- g0 ammo empty.

### Scoreboard

| Name             | Hits | + | - | Score |
|------------------|------|---|---|-------|
| Hurricane Howler | 10   | 2 | 0 | 60    |
| Air Blaze        | 0    | 0 | 2 | 0     |
