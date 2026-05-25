# Test 13 - Single-player upgrade and power-up checks

## Overview

- Used gun: g0 (Level 5)

## Run 1: Ammunition upgrade

- Mode: single player game
- Upgrade: ammu
- Power-Ups selected: top row 2nd from left
- State: 13 ammu, 10 health
- Event: receive 1 hit
- Action: shoot ships and reload
- Result: 4613 points
- XP: 136 xp --> 2122 xp

## Run 2: Health upgrade

- Reset upgrade
- Upgrade: health
- Power-up upgrade: health+reactivation time
- Mode: single player game
- Power-Ups selected: bottom row 1st from left, health+reactivation
- State: 10 ammu, 15 health
- Action: shoots enemies, reloads, collects health-regen (always 1 or 2 restored until full)
- Result: 901 points/110 xp --> 2232 xp

## Run 3: Damage upgrade

- Reset upgrade
- Upgrade: damage
- Power-up upgrade: health+reactivation time
- Mode: single player game
- Power-Ups selected: top row 1st from left, power-shot
- State: 10 ammu, 10 health
- Action: shoots enemies, reloads, no health-regen
- Ammo threshold: blinks green at 6
- Ammo threshold: yellow at 4
- Result: 41 points/9 xp --> 2241 xp

### Retry

- Power-Ups selected: top row 1st from left, super-shot
- Ammo threshold: blinks green at 6/10
- Ammo threshold: yellow at 4/10
- Ammo threshold: blinks yellow at 2/10
- Ammo threshold: red at 1/10
- Health threshold: blinks green at 6/10
- Health threshold: yellow at 4/10
- Health threshold: blinks yellow at 2/10
- Health threshold: blinks red at 1/10
- Result: 16 points/4 xp --> 2245 xp

## Run 4: Reload-time upgrade

- Reset upgrade
- Upgrade: reload time
- Power-up upgrade: usability (reload time, ammu, other blaster abilities)
- Mode: single player game
- Power-Ups selected: bottom row 1st from left, health
- State: 10 ammu, 10 health
- Action: shoots enemies, reloads, collects health-regen (if healed: always 1 restored until full)
- Result: 1051 points/97 xp --> 2342 xp

## Run 5: Multiple upgrades

- Reset upgrade
- Upgrade: reload time, reactivation time, health, ammu
- Power-up upgrade: usability
- Power-up upgrade: health
- Mode: single player game
- Power-Ups selected: top row 1st from left, power shot
- State: 10 ammu, 15 health
- Event: receive 5 damage (5*1)
- Action: shoots enemies, reloads, no health-regen
- Event: receive remaining 10 damage
- Result: 4201 points/119 xp --> 2461 xp

## Run 6: Reload-time, reactivation-time, and damage upgrades

- Reset upgrade
- Upgrade: reload time, reactivation time, damage
- Power-up upgrade: usability
- Power-up upgrade: attack
- Mode: single player game
- Power-Ups selected: top row 1st from left, power shot
- State: 10 ammu, 10 health
- Event: receive 10 damage (10*1)
- Result: 0 points/0 xp --> 2461 xp
