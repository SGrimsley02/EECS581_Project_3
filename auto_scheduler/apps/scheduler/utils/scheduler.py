'''
Name: apps/scheduler/scheduler.py
Description: Module for scheduling tasks
Authors: Hart Nurnberg, Audrey Pan, Kiara Grimsley, Ella Nguyen
Created: November 7, 2025
Last Modified: November 16, 2025
'''

from datetime import datetime, date, time, timedelta
from typing import List, Tuple, Dict, Optional
import copy
import pytz
from pytz import UTC
import logging

logger = logging.getLogger("apps.scheduler")

UTC = pytz.UTC

PRIORITY_ORDER = {
    "high": 0,
    "medium": 1,
    "low": 2
}

# Data structures used internally are as follows:
# BusySlot = (start_datetime, end_datetime)
# EventRequest = {
#   "title","description","duration_minutes","priority","event_type",
#   "date_start","date_end","time_start","time_end","split","split_minutes"
# }
# (date/time fields may be None or actual date/time objects)
# ScheduledEvent = {"title","description","start","end","event_type","priority"}

def _to_dt_utc(x) -> Optional[datetime]:
    """
    Accepts a datetime or ISO string and returns a timezone-aware UTC datetime.
    Used on events from ICS files.
    Returns None if x is empty.
    """
    logger.debug("_to_dt_utc: input=%r (type=%s)", x, type(x).__name__)
    if not x:
        logger.debug("_to_dt_utc: returning None (empty input)")
        return None
    if isinstance(x, datetime):
        out = x if x.tzinfo else x.replace(tzinfo=UTC)
        logger.debug("_to_dt_utc: datetime -> %s", out)
        return out
    # ISO string from import_ics (e.g., '2025-11-08T14:30:00+00:00')
    dt = datetime.fromisoformat(str(x))
    out = dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)
    logger.debug("_to_dt_utc: iso -> %s", out)
    return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)


def to_datetime(d: date, t: time) -> datetime:
    """
    Combine date + time into UTC-timezone-aware datetime
    Used on events created via form.
    If time is None use midnight.
    """
    logger.debug("to_datetime: d=%s t=%s", d, t)
    base = datetime.combine(d, t if t else time.min) # time.min is midnight
    out = base.replace(tzinfo=UTC)
    logger.debug("to_datetime: result=%s", out)
    return base.replace(tzinfo=UTC)

def merge_busy_slots(busy: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
    """Merge overlapping/adjacent busy intervals (assumes tz-aware)."""
    logger.debug("merge_busy_slots: in_count=%d", len(busy))
    if not busy:
        return []
    busy_sorted = sorted(busy, key=lambda x: x[0])
    merged = []
    cur_s, cur_e = busy_sorted[0]
    for s, e in busy_sorted[1:]:
        if s <= cur_e + timedelta(seconds=1):
            cur_e = max(cur_e, e)
        else:
            merged.append((cur_s, cur_e))
            cur_s, cur_e = s, e
    merged.append((cur_s, cur_e))
    logger.debug("merge_busy_slots: out_count=%d", len(merged))
    return merged

def invert_slots(busy: List[Tuple[datetime, datetime]], window_start: datetime, window_end: datetime) -> List[Tuple[datetime, datetime]]:
    """Return free slots inside [window_start, window_end) given merged busy intervals (all timezone-aware)."""
    logger.debug("invert_slots: window=[%s, %s) busy_count=%d", window_start, window_end, len(busy))
    free = []
    cur = window_start
    for s, e in busy:
        if e <= window_start or s >= window_end:
            continue
        s_clamped = max(s, window_start)
        e_clamped = min(e, window_end)
        if s_clamped > cur:
            free.append((cur, s_clamped))
        cur = max(cur, e_clamped)
    if cur < window_end:
        free.append((cur, window_end))
    logger.debug("invert_slots: free_count=%d", len(free))
    return free

def get_busy_from_imported(imported_events: List[dict]) -> List[Tuple[datetime, datetime]]:
    """
    Convert imported events (whose start/end are ISO strings from import_ics)
    into merged list of (start, end) UTC-timezone-aware datetimes.
    """
    logger.info("get_busy_from_imported: events_in=%d", len(imported_events))
    busy = []
    for ev in imported_events:
        s = _to_dt_utc(ev.get("start"))
        e = _to_dt_utc(ev.get("end"))
        if s and e and e > s:
            busy.append((s, e))
        else:
            logger.warning("get_busy_from_imported: skipped event name=%r start=%r end=%r", ev.get("name"), ev.get("start"), ev.get("end"))
    return merge_busy_slots(busy)

def expand_event_request(raw_event: dict):
    """
    Convert ISO strings in event_requests to python types (datetime or None).
    """
    logger.debug("expand_event_request: in=%r", raw_event)
    t = copy.copy(raw_event)
    # date_start/date_end are YYYY-MM-DD or None
    if t.get("date_start"):
        t["date_start"] = date.fromisoformat(t["date_start"])
    if t.get("date_end"):
        t["date_end"] = date.fromisoformat(t["date_end"])
    # time_start/time_end are HH:MM:SS or None
    if t.get("time_start"):
        t["time_start"] = time.fromisoformat(t["time_start"])
    if t.get("time_end"):
        t["time_end"] = time.fromisoformat(t["time_end"])
    t["duration_minutes"] = int(t.get("duration_minutes"))
    t["split_minutes"] = int(t["split_minutes"]) if t.get("split_minutes") else None
    t["split"] = bool(t.get("split"))
    logger.debug("expand_event_request: out=%r", t)
    return t

def generate_candidate_windows_for_event(event: dict, window_start: datetime, window_end: datetime) -> List[Tuple[datetime, datetime]]:
    """
    Build candidate day/time windows (tz-aware UTC).
    """
    logger.debug("generate_candidate_windows_for_event: title=%r window=[%s, %s)", event.get("title"), window_start, window_end)
    ds = event.get("date_start")
    de = event.get("date_end")
    ts = event.get("time_start")
    te = event.get("time_end")

    results = []

    start_date = ds if ds else window_start.date()
    end_date   = de if de else window_end.date()

    d = start_date
    one_day = timedelta(days=1)
    while d <= end_date:
        # TODO: Adjust time zone for the following (currently scheduling events 6 hours too early):
        day_start = to_datetime(d, ts if ts else time.min)
        day_end   = to_datetime(d, te if te else time.max)
        slot_s = max(day_start, window_start)
        slot_e = min(day_end, window_end)
        if slot_s < slot_e:
            results.append((slot_s, slot_e))
        d = d + one_day
    logger.debug("generate_candidate_windows_for_event: candidates=%d", len(results))
    return results

def split_into_chunks(duration_minutes: int, split: bool, split_minutes: Optional[int]) -> List[int]:
    """Return list of chunk durations (minutes). If split==False, returns [duration_minutes]."""
    logger.debug("split_into_chunks: duration=%d split=%s split_minutes=%r", duration_minutes, split, split_minutes)
    if not split:
        out = [duration_minutes]
        logger.debug("split_into_chunks: result=%r", out)
        return [duration_minutes]
    if not split_minutes:
        logger.error("split_into_chunks: split=True but split_minutes is None")
        raise ValueError("split_minutes required when split is True")
    chunks = []
    remaining = duration_minutes
    while remaining > 0:
        chunk = min(split_minutes, remaining)
        chunks.append(chunk)
        remaining -= chunk
    logger.debug("split_into_chunks: result=%r", chunks)
    return chunks

def schedule_events(
    event_requests_raw: List[dict],
    imported_events: List[dict],
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
) -> List[Dict]:
    """
    Main scheduling routine.
    Inputs:
      - event_requests_raw: session event dicts (ISO strings) -> will be expanded
      - imported_events: output of import_ics (used to build busy slots)
      - window_start/window_end: overall scheduling timeframe (default: now .. +14 days)
    Returns:
      - list of ScheduledEvent dicts: {"title","description","start","end","event_type","priority"}
    """
    logger.info("schedule_events: events_in=%d imported_in=%d window_start=%r window_end=%r",
                len(event_requests_raw), len(imported_events), window_start, window_end)

    # Ensure UTC-aware global window
    if window_start is None:
        window_start = datetime.now(UTC)
    else:
        window_start = _to_dt_utc(window_start)
    if window_end is None:
        window_end = window_start + timedelta(days=14)
    else:
        window_end = _to_dt_utc(window_end)

    busy = get_busy_from_imported(imported_events)
    current_busy = merge_busy_slots(busy[:])

    def compute_free():
        return invert_slots(merge_busy_slots(current_busy), window_start, window_end)

    priority_order = {"high": 0, "medium": 1, "low": 2}
    events = [expand_event_request(t) for t in event_requests_raw]
    events_sorted = sorted(
        events,
        key=lambda t: (
        PRIORITY_ORDER.get(t.get("priority", "medium"), 1),
        -int(t.get("duration_minutes", 0))
        )
    )
    
    scheduled_events = []
    logger.info("schedule_events: window=[%s, %s) initial_busy=%d events_sorted=%d",
                window_start, window_end, len(current_busy), len(events_sorted))

    for event in events_sorted:
        logger.info("schedule_events: placing event title=%r duration=%s priority=%s split=%s split_minutes=%r",
                    event.get("title"), event.get("duration_minutes"), event.get("priority"),
                    event.get("split"), event.get("split_minutes"))
        chunks = split_into_chunks(event["duration_minutes"], event.get("split", False), event.get("split_minutes"))
        for chunk_minutes in chunks:
            placed = False
            free_slots = compute_free()
            logger.debug("schedule_events: chunk=%d free_slots=%d", chunk_minutes, len(free_slots))
            candidates = []
            for free_s, free_e in free_slots:
                for cand in generate_candidate_windows_for_event(event, free_s, free_e):
                    candidates.append(cand)
            candidates.sort(key=lambda x: x[0])
            needed = timedelta(minutes=chunk_minutes)
            for cand_s, cand_e in candidates:
                if (cand_e - cand_s) >= needed:
                    start_dt = cand_s
                    end_dt = start_dt + needed
                    new_ev = {
                        "name": event.get("title"),
                        "description": event.get("description"),
                        "start": start_dt.isoformat(),  # tz-aware UTC
                        "end": end_dt.isoformat(),      # tz-aware UTC
                        "event_type": event.get("event_type"),
                        "priority": event.get("priority"),
                    }
                    scheduled_events.append(new_ev)
                    logger.info("schedule_events: scheduled title=%r start=%s end=%s", new_ev["name"], start_dt, end_dt)
                    current_busy.append((start_dt, end_dt))
                    current_busy = merge_busy_slots(current_busy)
                    placed = True
                    break
            if not placed:
                logger.warning("schedule_events: UNSCHEDULED title=%r minutes=%d (no fit)", event.get("title"), chunk_minutes)
                scheduled_events.append({
                    "name": event.get("title"),
                    "description": event.get("description"),
                    "start": None,
                    "end": None,
                    "event_type": event.get("event_type"),
                    "priority": event.get("priority"),
                    "unscheduled": True,
                    "requested_minutes": chunk_minutes
                })
    logger.info("schedule_events: done scheduled=%d (incl. unscheduled placeholders=%d)",
                sum(1 for e in scheduled_events if e.get("start")), len(scheduled_events))  # LOG
    return scheduled_events