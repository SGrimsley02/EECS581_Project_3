'''
Name: apps/scheduler/utils/stats.py
Description: Utility module with data analysis functions for
             scheduled events.
Authors: Audrey Pan
Created: November 22, 2025
Last Modified: November 22, 2025
'''
from collections import defaultdict
from datetime import datetime

def compute_time_by_event_type(events):
    """
    Given a list of event dicts (with 'start', 'end', and 'event_type'),
    return a list of { "event_type": str, "minutes": float } summaries.
    """
    totals = defaultdict(float)

    for ev in events:
        start = ev.get("start")
        end = ev.get("end")
        event_type = ev.get("event_type") or "Other"

        # You may already have datetime objects; if they're strings, parse them:
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end)

        duration = (end - start).total_seconds() / 60.0  # minutes
        if duration > 0:
            totals[event_type] += duration

    # Convert to a nicer list so it's easy to use in templates / charts
    return [
        {"event_type": etype, "minutes": round(minutes, 1)}
        for etype, minutes in totals.items()
    ]
