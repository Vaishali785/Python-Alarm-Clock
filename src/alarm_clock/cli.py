"""Interactive REPL for the alarm clock. Thin I/O shell around AlarmManager.

Alarms ring automatically: a background daemon thread checks every second
for due alarms from the moment the program starts, so no separate 'start'
command is needed — the REPL stays free for add/list/remove the whole time.
"""

import threading
import time as time_module
from datetime import datetime

from .manager import AlarmManager
from .time_utils import parse_time, format_time, describe_when

BANNER = "Alarm Clock CLI"

# Kept short on purpose — this prints at launch, and detailed usage isn't
# worth reading until someone actually needs it (that's what 'help' is for).
INTRO = "Type 'help' for commands, or jump right in: add <time> [label]"

HELP_TEXT = """
Commands:
  add <time> [label]   Set an alarm. Accepts 24h ("20:30") or 12h with am/pm
                        ("8:30 pm") — "8:30", "08:30" and "8:30 am" are all
                        the same time. Example: add 8:30 am Gym
  list                  Show active alarms (each marked Today or Tomorrow)
  remove <number>       Remove the alarm shown at that position in 'list'
  help                  Show this message again
  exit                  Quit

Alarms start ringing automatically as soon as they're set. They're always
shown back to you in 12-hour format (e.g. 8:30 PM).
""".strip("\n")


def _print_banner() -> None:
    print("=" * len(BANNER))
    print(BANNER)
    print("=" * len(BANNER))
    print()
    print(INTRO)
    print()


def _print_alarms(alarms, now) -> None:
    if not alarms:
        print("No active alarms.")
        print()
        return
    for i, alarm in enumerate(alarms, start=1):
        label = f" — {alarm.label}" if alarm.label else ""
        when = describe_when(alarm.next_trigger(now), now)
        print(f"  {i}. {format_time(alarm.alarm_time)}{label} — {when}")
    print()


def _handle_add(manager: AlarmManager, args: str) -> None:
    args = args.strip()
    if not args:
        print('Usage: add <time> [label]   e.g. add 8:30 am Wake up')
        print()
        return

    # The time token is 1 word ("8:30") or 2 ("8:30 am"); whatever follows
    # is the label. If the second word is an am/pm marker, it belongs to
    # the time, not the label.
    parts = args.split(maxsplit=1)
    time_str = parts[0]
    rest = parts[1] if len(parts) > 1 else ""

    if rest.lower().startswith(("am", "pm")):
        meridiem, *label_parts = rest.split(maxsplit=1)
        time_str = f"{time_str} {meridiem}"
        label = label_parts[0] if label_parts else ""
    else:
        label = rest

    try:
        alarm_time = parse_time(time_str)
    except ValueError as e:
        print(f"Couldn't set alarm: {e}")
        print()
        return

    alarm = manager.add(alarm_time, label.strip())
    now = datetime.now()
    when = describe_when(alarm.next_trigger(now), now)
    label_display = f" ({alarm.label})" if alarm.label else ""
    print(f"Alarm set for {format_time(alarm.alarm_time)}{label_display} — {when}.")
    print()


def _handle_remove(manager: AlarmManager, args: str) -> None:
    args = args.strip()
    if not args.isdigit():
        print("Usage: remove <number>   (see 'list' for numbers)")
        print()
        return
    try:
        removed = manager.remove(int(args))
        print(f"Removed alarm at {format_time(removed.alarm_time)}.")
    except IndexError as e:
        print(str(e))
    print()


def _ring(alarm) -> None:
    label = f" — {alarm.label}" if alarm.label else ""
    print()
    print("\a" + "!" * 40)
    print(f"ALARM: {format_time(alarm.alarm_time)}{label}")
    print("!" * 40)
    print()


def _checker_loop(manager: AlarmManager) -> None:
    """Runs continuously in a background thread for the life of the
    process, ringing alarms as they come due. Daemon thread — it's killed
    automatically when the main thread (the REPL) exits.

    Known trade-off: a ring can print in the middle of the REPL's input
    prompt, which can look slightly jumbled in the terminal. Solving that
    cleanly needs a fancier input setup (e.g. prompt_toolkit); not worth
    it for this exercise — noted here rather than silently ignored.
    """
    while True:
        now = datetime.now()
        for alarm in manager.due(now):
            _ring(alarm)
            manager.discard(alarm)
        time_module.sleep(1)


def main() -> None:
    manager = AlarmManager()
    threading.Thread(target=_checker_loop, args=(manager,), daemon=True).start()

    _print_banner()

    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("Goodbye.")
            break

        if not raw:
            continue

        command, *rest = raw.split(maxsplit=1)
        args = rest[0] if rest else ""
        command = command.lower()

        if command == "add":
            _handle_add(manager, args)
        elif command == "list":
            _print_alarms(manager.list(datetime.now()), datetime.now())
        elif command == "remove":
            _handle_remove(manager, args)
        elif command in ("help", "?"):
            print()
            print(HELP_TEXT)
            print()
        elif command in ("exit", "quit"):
            print("Goodbye.")
            break
        else:
            print(f"Unknown command: '{command}'. Type 'help' for options.")
            print()


if __name__ == "__main__":
    main()