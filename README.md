# Alarm Clock CLI

A time-boxed (30-minute) build exercise. This README captures the thinking _before_ writing code: what's in scope, what's deliberately cut, why, and how the remaining time is spent.

## 1. Problem framing

"Build an alarm clock" is underspecified on purpose. Before coding, I'm fixing the ambiguous points explicitly rather than guessing silently, since the reviewer cares about the decision process:

| Ambiguity                                             | Decision                                                                                                                                                                                                                                                                     | Why                                                                                                                                                                                                                           |
| ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Persistence across runs?                              | **No.** In-memory only for this session.                                                                                                                                                                                                                                     | Persistence (file/db) adds I/O, serialization, and corruption edge cases — not worth it in a 30-min budget. Called out as the #1 "next thing I'd add."                                                                        |
| One alarm or many?                                    | **Many**, since it's barely more work than one and is the more realistic case.                                                                                                                                                                                               |
| Interaction model?                                    | **Interactive REPL** (`add`, `list`, `remove`, `help`, `exit`) — **no separate `start` command.** A background thread checks for due alarms every second from the moment the program launches, so the REPL stays free to keep adding/listing/removing while alarms are live. | An alarm clock that makes you run a separate "start" step is one extra thing to forget. Ringing should just be a consequence of setting an alarm.                                                                             |
| How does "ringing" work?                              | Terminal bell (`\a`) + repeated printed banner, no audio file dependencies.                                                                                                                                                                                                  | Keeps it to stdlib only — no install step, no platform-specific audio libs to debug live.                                                                                                                                     |
| Alarm in the past (e.g. set 07:00 when it's 09:00)?   | **Roll forward to tomorrow**, same as a real alarm clock/phone.                                                                                                                                                                                                              |
| Timezones / DST?                                      | **Out of scope.** Uses local system time as-is.                                                                                                                                                                                                                              | Real alarm clocks don't ask for a timezone either; correctness here is a rabbit hole disproportionate to the exercise.                                                                                                        |
| Snooze?                                               | **Out of scope for MVP**, listed as a stretch goal if time remains.                                                                                                                                                                                                          |
| 12-hour or 24-hour format?                            | **Both accepted as input, normalized internally, always displayed as 12-hour AM/PM.** Stated in the `add` command's own help line — see §3a.                                                                                                                                 | Users type times in whichever format is natural to them; the tool shouldn't force one and silently misread the other.                                                                                                         |
| Does the user need to know which day an alarm is for? | **Yes — every alarm shows Today/Tomorrow**, both in the confirmation when it's set and in `list`.                                                                                                                                                                            | Since alarms silently roll to the next day when the time's already passed, hiding that would be confusing — the user should never have to guess whether "8:30" meant this morning or tomorrow morning.                        |
| How much detail should the startup banner show?       | **Minimal.** A one-line hint (`Type 'help' for commands...`); the full command list and format explanation only appear on demand via `help`.                                                                                                                                 | Nobody reads a wall of instructions before touching a new CLI — they skim past it to try something. Front-loading detail just gets skipped; putting it behind `help` means it's there exactly when someone actually needs it. |

## 2. MVP scope

**In scope:**

- Add an alarm: 24h or 12h input, normalized (see §3a) + optional label
- Adding an alarm shows the time **and whether it's Today or Tomorrow**
- List active alarms, sorted by next trigger time, each labeled Today/Tomorrow
- Remove an alarm by index
- Alarms ring automatically — a background thread checks every second from launch, no `start` step required
- Ringing = clear visual + audible signal, alarm then removed (one-shot) from the active list
- Ctrl+C exits cleanly at any point
- Input validation with a clear error message, loop re-prompts instead of crashing

**Explicitly out of scope (and why):**

- Persistence (see table above)
- Recurring/repeating alarms (daily, weekdays) — adds a whole scheduling model; one-shot alarms already exercise the core logic
- Snooze — secondary interaction, not core to "does it wake you up at the right time"
- Sound files / media playback — dependency risk under time pressure
- Config files, logging framework, packaging as installable CLI

This scope is intentionally small enough to finish _and_ leave time to test it, rather than leaving something half-working.

## 3. Architecture

```
project root/
├── main.py                     # entry point — adds src/ to path, calls alarm_clock.cli.main()
├── src/
│   └── alarm_clock/
│       ├── __init__.py
│       ├── time_utils.py       # parse_time() / format_time() — parsing & normalization only
│       ├── manager.py          # Alarm dataclass + AlarmManager: add/remove/list/due (no I/O)
│       └── cli.py              # REPL loop: parses commands, talks to AlarmManager, prints
├── tests/
│   └── __init__.py             # structure in place; no tests added yet (see §7)
└── README.md
```

`src/` (logic) and `tests/` are kept separate per the existing repo convention, even though no
tests are written for this exercise — the structure should already fit them in when they are.

Within `src/alarm_clock`, three layers, each with one job:

- `time_utils.py` — turns raw user text into a `datetime.time` (and back to display text, including the Today/Tomorrow label). Isolated because parsing/normalization is fiddly and is exactly the kind of thing worth testing on its own.
- `manager.py` — scheduling logic (add/remove/list/what's due). Zero `print`/`input` calls, so it's testable without mocking stdin/stdout. Since alarms are now checked by a background thread running concurrently with the REPL's main thread, its internal list is protected by a lock (`threading.RLock`) — this wasn't needed under the old blocking-`start` model, where only one thread ever touched it.
- `cli.py` — thin I/O shell: reads commands, calls into the above, formats output, and owns the background checker thread.

## 3a. Time format handling

- **Input:** either 24-hour (`8:30`, `08:30`, `20:30`) or 12-hour with an am/pm suffix (`8:30 am`, `8:30pm`, `8 PM`). A bare value with no am/pm is always read as 24-hour.
- **Normalization:** `8:30`, `08:30`, and `8:30 am` all resolve to the identical internal time — they describe the same moment (eight-thirty in the morning) under either convention, so there's no ambiguity to resolve, just formatting differences to absorb.
- **Display:** alarms are always shown back to the user in 12-hour AM/PM format, regardless of how they were entered, plus a Today/Tomorrow tag (see §1).
- **Where this is documented for the user:** folded directly into the `add` command's own line in `help` — not a separate paragraph the user has to notice, and not shown unprompted at startup (see the banner decision in §1).

## 3b. UI readability

The REPL prints a blank line after every command's output (success or error) and after the banner/help text, so each turn is visually separated from the next in the terminal rather than running together.

**Auto-start via background thread:**

```
on launch:
    spawn daemon thread running:
        loop forever:
            now = current time
            for each alarm due this minute:
                ring it, remove from active list
            sleep(1)
    enter the REPL's input loop on the main thread
```

Daemon thread so it's killed automatically when the REPL exits — no manual shutdown needed. Known trade-off, called out rather than hidden: a ring can print in the middle of the REPL's `> ` input prompt, which can look slightly jumbled in the terminal. A fully clean fix needs a more capable input setup (e.g. `prompt_toolkit`); not proportionate to this exercise.

## 4. Edge cases considered

- Malformed time input (`"25:99"`, `"7:30xm"`, empty string) → validation error, re-prompt, don't crash
- Alarm time equal to "right now" → should still ring this minute, and should still be labeled **Today**, not Tomorrow (see next point)
- **Found via testing:** the "already passed" check that decides Today vs. Tomorrow originally compared full timestamps (including seconds), while the ringing check only compares hour:minute. Result: setting an alarm for the current minute but a few seconds in could show "Tomorrow" and then ring immediately anyway — a real contradiction. Fixed by comparing both at minute granularity.
- Alarm time already passed today → rolls to tomorrow (see decision table)
- Two alarms set for the same time → both ring, independently
- `remove` with an out-of-range index → error message, no crash
- Concurrent access to the alarm list (REPL thread + background checker thread) → guarded by a lock in `AlarmManager` (see §3)
- Ctrl+C at the input prompt → caught, exits with a clean message instead of a stack trace
- Duplicate `add` of the identical time+label → allowed (no dedup rule was given; treated as user's call)

## 5. Time budget (30 min total)

| Step                                            | Time   |
| ----------------------------------------------- | ------ |
| Requirements, scope, README (this doc)          | ~7 min |
| `manager.py` + `time_utils.py` (core logic)     | ~8 min |
| `cli.py` + `main.py` (REPL, background ringing) | ~8 min |
| Manual test pass against the edge cases above   | ~5 min |
| Final polish + record walkthrough               | ~2 min |

## 6. How to run

```bash
python main.py
```

Commands inside the REPL: `add <time> [label]`, `list`, `remove <number>`, `help`, `exit`.
Time can be entered as `8:30`, `08:30`, `8:30 am`, or `20:30` — all handled the same way (see §3a).
Alarms start ringing automatically as soon as they're set.

## 7. What I'd add with more time

1. Persistence (JSON file) so alarms survive restarts
2. Recurring alarms (daily / specific weekdays)
3. Snooze
4. Unit tests in `tests/` for `manager.py` and `time_utils.py` — both were written with no I/O specifically so this is straightforward to add later
5. Non-interactive mode (`python main.py add 07:30 Gym`) for scriptability
