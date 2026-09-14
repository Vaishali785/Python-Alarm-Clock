"""Time parsing and normalization.

Format convention (also shown to the user in the CLI's help text):

  - A bare "HH:MM" value with no am/pm suffix is read as 24-hour time.
  - A value with an am/pm suffix is read as 12-hour time.

These two conventions agree by construction: 24-hour "08:30" and 12-hour
"8:30 am" both mean eight-thirty in the morning. So "8:30", "08:30", and
"8:30 am" all normalize to the exact same internal time — which is the
behavior requested for this exercise.

Alarms are always *displayed* back to the user in 12-hour AM/PM format,
since that's what most people read faster at a glance.
"""

from datetime import datetime, time


def parse_time(raw: str) -> time:
    """Parse user input into a time object.

    Accepts:
      - 24-hour, no am/pm: "8:30", "08:30", "20:30"
      - 12-hour, with am/pm: "8:30 am", "8:30pm", "8 PM"

    Raises ValueError with a human-readable message on bad input.
    """
    text = raw.strip()
    if not text:
        raise ValueError("Time cannot be empty.")

    has_meridiem = text.lower().endswith(("am", "pm"))

    if has_meridiem:
        # Normalize spacing so "8:30am", "8:30 am", "8:30AM" all match the
        # same strptime format: collapse internal spaces, then re-insert
        # exactly one space before the AM/PM marker.
        compact = text.upper().replace(" ", "")
        suffix = compact[-2:]
        body = compact[:-2]
        candidate = f"{body} {suffix}"
        for fmt in ("%I:%M %p", "%I %p"):
            try:
                return datetime.strptime(candidate, fmt).time()
            except ValueError:
                continue
        raise ValueError(
            f"Couldn't parse '{raw}' as a 12-hour time (e.g. '8:30 AM')."
        )

    try:
        return datetime.strptime(text, "%H:%M").time()
    except ValueError:
        raise ValueError(
            f"Couldn't parse '{raw}' as a 24-hour time (e.g. '08:30' or '20:30')."
        )


def format_time(t: time) -> str:
    """Display format: 12-hour clock with AM/PM, e.g. '8:30 AM'."""
    return t.strftime("%I:%M %p").lstrip("0")


def describe_when(target: datetime, now: datetime) -> str:
    """'Today (Sep 14)' or 'Tomorrow (Sep 15)', relative to now's date.

    Alarms only ever roll forward at most one day (see
    Alarm.next_trigger in manager.py), so no case beyond these two is
    needed here.
    """
    day_word = "Today" if target.date() == now.date() else "Tomorrow"
    return f"{day_word} ({target.strftime('%b %d')})"