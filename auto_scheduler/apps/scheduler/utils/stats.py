'''
Name: apps/scheduler/utils/stats.py
Description: Utility module with data analysis functions for
             scheduled events.
Authors: Audrey Pan
Created: November 22, 2025
Last Modified: November 24, 2025
'''
from collections import defaultdict
from datetime import datetime, date, timedelta


from collections import defaultdict
from datetime import datetime


def compute_time_by_event_type(events):
    """
    Given a list of event dicts, return a list of
    { "event_type": str, "minutes": float } summaries.

    Prefer an explicit 'duration_minutes' field if present;
    otherwise fall back to (end - start).
    """
    totals = defaultdict(float)

    for ev in events:
        event_type = ev.get("event_type") or "Other"

        # Prefer explicit duration if available
        dur = ev.get("duration_minutes")
        if dur is not None:
            try:
                dur = float(dur)
            except (TypeError, ValueError):
                dur = None

        # If no usable duration_minutes, try start/end
        if dur is None:
            start = ev.get("start")
            end = ev.get("end")

            if not start or not end:
                # nothing we can do for this event
                continue

            # Parse strings into datetimes if needed
            if isinstance(start, str):
                try:
                    start = datetime.fromisoformat(start)
                except ValueError:
                    continue

            if isinstance(end, str):
                try:
                    end = datetime.fromisoformat(end)
                except ValueError:
                    continue

            if not isinstance(start, datetime) or not isinstance(end, datetime):
                continue

            dur = (end - start).total_seconds() / 60.0  # minutes

        # Add to totals if duration is positive
        if dur and dur > 0:
            totals[event_type] += dur

    # Convert to a nicer list so it's easy to use in templates / charts
    return [
        {"event_type": etype, "minutes": round(minutes, 1)}
        for etype, minutes in totals.items()
    ]



def compute_study_minutes_by_day(events, study_event_type="Study"):
    """
    Aggregate total study minutes per calendar day.
    Only counts events where event_type == study_event_type.
    Returns a dict mapping date -> total minutes for that date.
    """
    minutes_by_day = {}

    for ev in events:
        if ev.get("event_type") != study_event_type:
            continue

        start_str = ev.get("start")
        end_str = ev.get("end")
        if not start_str or not end_str:
            continue

        try:
            start_dt = datetime.fromisoformat(start_str)
            end_dt = datetime.fromisoformat(end_str)
        except ValueError:
            continue

        if end_dt <= start_dt:
            continue

        minutes = (end_dt - start_dt).total_seconds() / 60.0
        if minutes <= 0:
            continue

        day = start_dt.date()
        minutes_by_day[day] = minutes_by_day.get(day, 0) + minutes

    return minutes_by_day


def compute_monthly_heatmap_data(events, today=None, study_event_type="Study"):
    """
    Build data for a monthly study-heatmap.

    Returns a dict with:
      - weeks: list of week rows, each row is a list of 7 entries or None
        Each entry is:
          { "date": date, "day": int, "minutes": int, "hours": float, "bucket": int }
      - has_data: True if any study minutes exist for the month
      - month_name: e.g. "November"
      - year: integer year
      - summary: {
            "total_minutes", "total_hours",
            "days_with_study",
            "avg_minutes_per_study_day", "avg_hours_per_study_day"
        }
    """
    if not today:
        today = date.today()

    year, month = today.year, today.month
    first_day = date(year, month, 1)

    # Compute last day of the month
    if month == 12:
        next_first = date(year + 1, 1, 1)
    else:
        next_first = date(year, month + 1, 1)
    last_day = next_first - timedelta(days=1)

    # Total study minutes per day for this month
    minutes_by_day = compute_study_minutes_by_day(events, study_event_type=study_event_type)
    month_minutes = {
        d: m for d, m in minutes_by_day.items()
        if first_day <= d <= last_day
    }
    max_minutes = max(month_minutes.values()) if month_minutes else 0

    def bucket_for_minutes(m):
        if m <= 0 or max_minutes <= 0:
            return 0
        ratio = m / max_minutes
        if ratio <= 0.25:
            return 1
        elif ratio <= 0.5:
            return 2
        elif ratio <= 0.75:
            return 3
        else:
            return 4

    # Build grid of weeks
    weeks = []
    week = []

    # Leading blanks before the first day (Mon=0)
    first_weekday = first_day.weekday()
    for _ in range(first_weekday):
        week.append(None)

    current = first_day
    while current <= last_day:
        mins = month_minutes.get(current, 0.0)
        hours = round(mins / 60.0, 1) if mins > 0 else 0.0
        entry = {
            "date": current,
            "day": current.day,
            "minutes": int(round(mins)),
            "hours": hours,
            "bucket": bucket_for_minutes(mins),
        }
        week.append(entry)

        if len(week) == 7:
            weeks.append(week)
            week = []

        current += timedelta(days=1)

    # Trailing blanks
    if week:
        while len(week) < 7:
            week.append(None)
        weeks.append(week)

    # Summary stats
    total_minutes = sum(month_minutes.values()) if month_minutes else 0.0
    days_with_study = sum(1 for m in month_minutes.values() if m > 0)
    avg_per_study_day = (total_minutes / days_with_study) if days_with_study else 0.0

    summary = {
        "total_minutes": int(round(total_minutes)),
        "total_hours": round(total_minutes / 60.0, 1),
        "days_with_study": days_with_study,
        "avg_minutes_per_study_day": round(avg_per_study_day, 1),
        "avg_hours_per_study_day": round(avg_per_study_day / 60.0, 2) if days_with_study else 0.0,
    }

    return {
        "weeks": weeks,
        "has_data": bool(month_minutes),
        "month_name": first_day.strftime("%B"),
        "year": year,
        "summary": summary,
    }
