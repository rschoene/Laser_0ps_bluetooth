0: App searching for devices
0: App sees g0 as "Laser" "Zombie"
0: Start test
(1: enabled)
0: Test trigger
0: Test trigger
0: Test trigger
0: App: pressed Confirm
0: App: rename? Yes
0: Selected Name: "Hurricane" "Howler" Index 17, Index 19
0: level 3
0: App unused points
0: Power-Up: Attack
0: Upgrade: Health
0: Upgrade: Munition
0: Upgrade: Damage
1: App searching for devices
1: App lists g0 as "Laser" "Zombie"
1: App lists g1 as "Frost" "Falcon"
1: Start test
1: Test trigger
1: Test trigger
1: Test trigger
1: Test trigger
1: App: pressed Confirm
1: App: rename? Yes
1: Selected Name: "Air" "Blaze" Index 1, Index 3
0: lost connection
1: level 2
1: App unused points
1: Power-Up: Attack
1: Upgrade: Damage
2: App searching for devices
2 App lists g2 as unnamed (Bt-MAC)
2: Start test
2: App: pressed Confirm
2: App: rename? Yes
2: Selected Name: "Atom" "Beast" Index 2, Index 4
1: lost connection
2: level 1
2: Power-Up: Attack
3: App searching for devices
3 App lists g3 as "Zinc" "Zenith"
3: Start test
3: Test trigger
3: Test trigger
3: Test trigger
3: Test trigger
3: Test trigger
3: Test trigger
3: Test trigger
3: Test trigger
3: Test trigger
3: Test trigger
3: App: pressed Confirm
3: App: rename? Yes
3: Selected Name: "Burst" "Defender" Index 2, Index 9
2: lost connection
3: level 2
3: Power-Up: Attack
3: Upgrade: Reload

## Protocol Notes

Detailed protocol analysis, message sequencing, and byte-level field definitions now live in [traffic_definition.md](traffic_definition.md).

Key takeaways from this test:
- Startup sequence is `35` from host on handle `0x0026`, `35 ...` from gun on handle `0x0023`, then `5b1f` from host on `0x0026`.
- The 13-byte config writes on handle `0x0026` use byte 8 as the level field.
- The 1-byte gun notification `49` on handle `0x0023` matches trigger/fire events.
