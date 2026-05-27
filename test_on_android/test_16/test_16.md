g2 single player games

g2: reset upgrades
g2: no upgrades: Ammu: 10, Damage 2, Health 10, Level 12, Name Atom Beast, Reactivation Time 10 s
app: start game
app: cancel game

g2: upgrade Health 1: Ammu: 10, Damage 2, Health 15, Level 12, Name Atom Beast, Reactivation Time 10 s
app: start game
app: cancel game

g2: upgrade Health 2: Ammu: 10, Damage 2, Health 20, Level 12, Name Atom Beast, Reactivation Time 10 s
app: start game
app: cancel game

g2: reset upgrades
g2: upgrade Ammu 1: Ammu: 13, Damage 2, Health 10, Level 12, Name Atom Beast, Reactivation Time 10 s
app: start game
app: cancel game

g2: upgrade Ammu 2: Ammu: 16, Damage 2, Health 10, Level 12, Name Atom Beast, Reactivation Time 10 s
app: start game
app: cancel game

g2: reset upgrades
g2: upgrade Damage 1: Ammu: 10, Damage 3, Health 10, Level 12, Name Atom Beast, Reactivation Time 10 s
app: start game
app: cancel game

g2: upgrade Damage 2: Ammu: 10, Damage 4, Health 10, Level 12, Name Atom Beast, Reactivation Time 10 s
app: start game
app: cancel game

g2: reset upgrades
g2: upgrade Reactivation 1: Ammu: 10, Damage 2, Health 10, Level 12, Name Atom Beast, Reactivation Time 9 s
app: start game
app: cancel game

g2: upgrade Reactivation 2: Ammu: 10, Damage 2, Health 10, Level 12, Name Atom Beast, Reactivation Time 8 s
app: start game
app: cancel game

g2: reset upgrades
(last two runs, I tried to change Reload Time, with no change in UI and no change in 36 encoding)

```
$ python scripts/log_runs_with_context.py --describe-detailed --root test_on_android/test_16 | grep " 360" | awk '{print $6}' 
36030a020203000a0c03050004
36030a020203000f0c03050004
36030a02020300140c03050004
36030d020203000a0c03050004
360310020203000a0c03050004
36030a030203000a0c03050004
36030a040203000a0c03050004
36030a020203000a0c03050003
36030a020203000a0c03050002
36030a020203000a0c03050004
36030a020203000a0c03050004
#(last two I tried to change Reload Time, with no change in UI and no change in 36 encoding)
# candidate correlation
3603AADD020300HHLLNNMM00RR
```

Candidate correlation:
- AA: Ammu
- DD: Damage
- HH: Health
- LL: Level
- NN: Name1
- MM: Name2
- RR: related to Reactivation Time (04: 10s, 03: 9s, 02: 8s)