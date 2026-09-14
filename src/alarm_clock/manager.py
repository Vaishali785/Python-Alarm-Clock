"""Alarm scheduling logic.

Deliberately has no print()/input() calls — this is the part worth unit
testing, so it's kept independent of the CLI/I/O layer in cli.py.

Thread-safe: alarms now ring automatically via a background checker thread
(see cli.py) that runs concurrently with the REPL's main thread, so reads
and writes to the alarm list are protected by a lock.
"""

# Needed because AlarmManager defines a method named `list`, which shadows
# the builtin `list` inside the class body — without this, the `list[Alarm]`
# type hint on due() fails to resolve at class-definition time.
from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from itertools import count


@dataclass
class Alarm:
    id: int
    alarm_time: time
    label: str = ""

    def next_trigger(self, now: datetime) -> datetime:
        """Next datetime (today or tomorrow) this alarm should fire.

        Compared at minute granularity, not seconds — due() below also
        only matches on hour:minute, so a target time equal to the
        *current* minute must count as "still today, about to ring" here
        too. Using full datetime precision would sometimes roll this to
        tomorrow while due() rings it immediately in the same minute —
        a real inconsistency caught by testing.
        """
        candidate = now.replace(
            hour=self.alarm_time.hour,
            minute=self.alarm_time.minute,
            second=0,
            microsecond=0,
        )
        now_minute = now.replace(second=0, microsecond=0)
        if candidate < now_minute:
            candidate += timedelta(days=1)
        return candidate


class AlarmManager:
    """Holds the set of active alarms for this session (in-memory only —
    no persistence, by design; see README)."""

    def __init__(self):
        self._alarms: list[Alarm] = []
        self._ids = count(1)
        self._lock = threading.RLock()

    def add(self, alarm_time: time, label: str = "") -> Alarm:
        with self._lock:
            alarm = Alarm(id=next(self._ids), alarm_time=alarm_time, label=label)
            self._alarms.append(alarm)
            return alarm

    def remove(self, index: int) -> Alarm:
        """Remove by 1-based display position, as shown by list()."""
        with self._lock:
            if index < 1 or index > len(self._alarms):
                raise IndexError(f"No alarm at position {index}.")
            return self._alarms.pop(index - 1)

    def list(self, now: datetime) -> list[Alarm]:
        """Active alarms sorted by how soon they'll next trigger."""
        with self._lock:
            return sorted(self._alarms, key=lambda a: a.next_trigger(now))

    def due(self, now: datetime) -> list[Alarm]:
        """Alarms whose hour+minute matches now — i.e. should ring this tick."""
        with self._lock:
            return [
                a for a in self._alarms
                if a.alarm_time.hour == now.hour and a.alarm_time.minute == now.minute
            ]

    def discard(self, alarm: Alarm) -> None:
        with self._lock:
            if alarm in self._alarms:
                self._alarms.remove(alarm)

    def is_empty(self) -> bool:
        with self._lock:
            return not self._alarms