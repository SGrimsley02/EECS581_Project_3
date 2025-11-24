'''
Name: apps/scheduler/utils/scheduler.py
Description: Module for scheduling tasks
Authors: Hart Nurnberg, Audrey Pan, Kiara Grimsley, Ella Nguyen
Created: November 7, 2025
Last Modified: November 22, 2025
'''

from datetime import datetime, date, time, timedelta
from typing import List, Tuple, Dict, Optional
import copy
import pytz
from pytz import UTC
import logging
from .constants import PRIORITY_ORDER

logger = logging.getLogger("apps.scheduler")

UTC = pytz.UTC


def preview_schedule_order(event_requests_raw):
    # If you already have expand_event_request, keep using it; else pass through
    events = [expand_event_request(t) for t in event_requests_raw]
    return sorted(events, key=schedule_sort_key)

# Used in views.py for the Export page to preview the order of events
def schedule_sort_key(t):
    pr = PRIORITY_ORDER.get(t.get("priority", "medium"), 1)
    dur = int(t.get("duration_minutes", 0) or 0)
    return (pr, -dur)

# Data structures used internally are as follows:
# BusySlot = (start_datetime, end_datetime)
# EventRequest = {
#   "title","description","duration_minutes","priority","event_type",
#   "date_start","date_end","time_start","time_end","split","split_minutes",
#   "recurring", "recurring_until"
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


# Modified to_datetime to accept a local timezone and return UTC-aware datetime
def to_datetime(d: date, t: time, tzinfo_local=None) -> datetime:
	"""
	Combine date + time into a timezone-aware datetime in UTC.
	If tzinfo_local is provided it is treated as the local timezone for the supplied date+time.
	If time is None use midnight.
	"""
	logger.debug("to_datetime: d=%s t=%s tz=%r", d, t, tzinfo_local)
	base = datetime.combine(d, t if t else time.min)
	# Normalize tzinfo_local: accept string or tzinfo object
	if tzinfo_local is None:
		local_tz = UTC
	elif isinstance(tzinfo_local, str):
		local_tz = pytz.timezone(tzinfo_local)
	else:
		local_tz = tzinfo_local
	# For pytz timezones use localize; for others set tzinfo directly
	if hasattr(local_tz, "localize"):
		local_dt = local_tz.localize(base)
	else:
		local_dt = base.replace(tzinfo=local_tz)
	out = local_dt.astimezone(UTC)
	logger.debug("to_datetime: result=%s (from local %s)", out, local_dt)
	return out

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
    t["recurring"] = bool(t.get("recurring"))
    if t.get("recurring_until"):
        t["recurring_until"] = date.fromisoformat(t["recurring_until"])
    logger.debug("expand_event_request: out=%r", t)
    return t

def generate_candidate_windows_for_event(event: dict, window_start: datetime, window_end: datetime, wake_time: Optional[time] = None, bed_time: Optional[time] = None, local_tz=None) -> List[Tuple[datetime, datetime]]:
    """
    Build candidate day/time windows (tz-aware UTC). Optionally clamp each day's candidate to [wake_time, bed_time).
    Interpret the provided times in the user's local timezone (local_tz) if given.
    """
    logger.debug("generate_candidate_windows_for_event: title=%r window=[%s, %s) wake=%r bed=%r", event.get("title"), window_start, window_end, wake_time, bed_time)
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
        # Interpret day start/end in the user's local timezone (if provided) so times like 08:00 local map correctly to UTC
        day_start = to_datetime(d, ts if ts else time.min, tzinfo_local=local_tz)
        day_end   = to_datetime(d, te if te else time.max, tzinfo_local=local_tz)
        slot_s = max(day_start, window_start)
        slot_e = min(day_end, window_end)

        # clamp to wake/bed if given
        if wake_time:
            wake_dt = to_datetime(d, wake_time, tzinfo_local=local_tz)
        else:
            wake_dt = None
        if bed_time:
            bed_dt = to_datetime(d, bed_time, tzinfo_local=local_tz)
            # if bed <= wake -> bed crosses to next day
            if wake_dt and bed_dt <= wake_dt:
                bed_dt = bed_dt + timedelta(days=1)
        else:
            bed_dt = None

        if wake_dt or bed_dt:
            # build clamp interval for this day
            clamp_s = wake_dt if wake_dt else datetime.min.replace(tzinfo=UTC)
            clamp_e = bed_dt if bed_dt else datetime.max.replace(tzinfo=UTC)
            # Note: if clamp interval doesn't intersect [slot_s, slot_e), skip
            slot_s = max(slot_s, clamp_s)
            slot_e = min(slot_e, clamp_e)

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

def convert_time_of_day_rankings(preferences: dict) -> List[Tuple[int, Tuple[time, time]]]:
    """
    Convert time of day rankings from preferences into a sorted list of (rank, (start_time, end_time)).
    Lower numeric rank is considered better (preferred earlier). Returns list sorted by rank ascending.
    """
    # List of (preference key, (start_time, end_time))
    time_windows = [
        ('early_morning_rank', (time(5), time(9))),
        ('late_morning_rank', (time(9), time(12))),
        ('afternoon_rank', (time(12), time(16))),
        ('evening_rank', (time(16), time(20))),
        ('night_rank', (time(20), time(0))),
        ('late_night_rank', (time(0), time(5))),
    ]
    ranked_windows = []
    for key, window in time_windows:
        rank = int(preferences[key]) if preferences and key in preferences else 0
        ranked_windows.append((rank, window))
    # sort by numeric rank ascending (lower rank = more preferred)
    ranked_windows.sort(key=lambda x: x[0])
    logger.debug("convert_time_of_day_rankings: ranked_windows=%r", ranked_windows)
    return ranked_windows

def convert_blackout_days(preferences: dict) -> List[int]:
    """
    Convert blackout days from preferences into a list of integers (0=Monday, 6=Sunday).
    Returns empty list if no blackout days specified.
    """
    WEEKDAY_MAP = {
        'mon': 0, 'monday': 0,
        'tue': 1, 'tuesday': 1,
        'wed': 2, 'wednesday': 2,
        'thu': 3, 'thursday': 3,
        'fri': 4, 'friday': 4,
        'sat': 5, 'saturday': 5,
        'sun': 6, 'sunday': 6,
    }
    if not preferences or "blackout_days" not in preferences:
        return []
    days = preferences["blackout_days"]
    result = []
    if isinstance(days, list):
        for d in days:
            if d in WEEKDAY_MAP:
                result.append(WEEKDAY_MAP[d])
    else:
        logger.error("convert_blackout_days: expected list for blackout_days, got %s", type(days).__name__)
        return []
    logger.debug("convert_blackout_days: result=%r", result)
    return result

def score_and_sort_candidates(candidates, time_of_day_ranks, local_tz):
	"""
	Given a list of candidate (start, end) tuples and time_of_day_ranks,
	return candidates sorted by score (descending), then earliest start.
	local_tz is used to interpret time-of-day windows in local time.
	"""
	scored = []
	total_weights = len(time_of_day_ranks) if time_of_day_ranks else 0
	for cand_s, cand_e in candidates:
		score = 0.0
		# For each ranked window compute overlap (minutes) and weight by rank ordering (earlier in list = more preferred)
		for idx, (rank, (t_start, t_end)) in enumerate(time_of_day_ranks):
			weight = total_weights - idx
			day = cand_s.astimezone(local_tz).date() if local_tz is not None and local_tz != UTC else cand_s.date()
			# Build window datetimes for the candidate's start date in local_tz then convert to UTC
			win_s = to_datetime(day, t_start, tzinfo_local=local_tz)
			win_e = to_datetime(day, t_end, tzinfo_local=local_tz)
			# if window crosses midnight (end <= start), push end to next day
			if win_e <= win_s:
				win_e = win_e + timedelta(days=1)
			# compute overlap in minutes
			ov_s = max(cand_s, win_s)
			ov_e = min(cand_e, win_e)
			overlap_min = max(0.0, (ov_e - ov_s).total_seconds() / 60.0)
			score += weight * overlap_min
		scored.append((score, cand_s, cand_e))
	# sort by score desc, then earliest start
	scored.sort(key=lambda x: (-x[0], x[1]))
	return [(s, e) for _, s, e in scored]

# NEW helper: parse preference time (accept time object or ISO string)
def _parse_pref_time(val) -> Optional[time]:
	if not val:
		return None
	if isinstance(val, time):
		return val
	# Expect "HH:MM" or "HH:MM:SS"
	return time.fromisoformat(str(val))

# NEW helper: determine local timezone (preferences may include 'timezone' string)
def _get_local_tz(preferences) -> object:
	# preferences['timezone'] may be a tz name (e.g., 'America/Los_Angeles') or None.
	if preferences and preferences.get("timezone"):
		try:
			return pytz.timezone(preferences.get("timezone"))
		except Exception:
			logger.warning("invalid timezone in preferences: %r, falling back to system timezone", preferences.get("timezone"))
	# Fallback to system local timezone tzinfo
	try:
		return datetime.now().astimezone().tzinfo
	except Exception:
		return UTC

def find_preferred_subwindow(cand_s: datetime, cand_e: datetime, needed: timedelta, time_of_day_ranks: List[Tuple[int, Tuple[time, time]]], wake_time: Optional[time] = None, bed_time: Optional[time] = None, local_tz=None):
	logger.debug("find_preferred_subwindow: cand=[%s,%s) needed=%s ranks=%d", cand_s, cand_e, needed, len(time_of_day_ranks) if time_of_day_ranks else 0)
	if not time_of_day_ranks:
		return None
	# Number of days spanned by candidate (inclusive)
	num_days = max(0, (cand_e.date() - cand_s.date()).days)
	for day_offset in range(num_days + 1):
		# interpret day in local timezone for proper day boundaries
		local_day = (cand_s.astimezone(local_tz).date() if local_tz else cand_s.date()) + timedelta(days=day_offset)
		day = local_day

		# compute day's wake/bed datetimes if provided
		day_wake = to_datetime(day, wake_time, tzinfo_local=local_tz) if wake_time else None
		day_bed  = to_datetime(day, bed_time, tzinfo_local=local_tz) if bed_time else None
		if day_wake and day_bed and day_bed <= day_wake:
			day_bed = day_bed + timedelta(days=1)

		for _rank, (t_start, t_end) in time_of_day_ranks:
			win_s = to_datetime(day, t_start, tzinfo_local=local_tz)
			win_e = to_datetime(day, t_end, tzinfo_local=local_tz)
			# handle windows that cross midnight
			if t_end <= t_start:
				win_e = win_e + timedelta(days=1)
			# intersection of candidate and this preferred window
			ov_s = max(cand_s, win_s)
			ov_e = min(cand_e, win_e)

			# also ensure it lies within wake/bed if those exist for this day
			if day_wake:
				ov_s = max(ov_s, day_wake)
			if day_bed:
				ov_e = min(ov_e, day_bed)

			if (ov_e - ov_s) >= needed:
				logger.debug("find_preferred_subwindow: found window [%s,%s) inside preferred [%s,%s)", ov_s, ov_s + needed, win_s, win_e)
				return (ov_s, ov_s + needed)
	logger.debug("find_preferred_subwindow: no preferred fit found")
	return None
def schedule_single_event(
    event: dict,
    chunk_minutes: int,
    current_busy: List[Tuple[datetime, datetime]],
    scheduled_events: List[dict],
    window_start: datetime,
    window_end: datetime,
    range_start: Optional[datetime] = None,
    range_end: Optional[datetime] = None,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Schedule a single chunk of chunk_minutes minutes for event.
    - Looks for a free slot within [range_start, range_end) if provided,
      otherwise within the global [window_start, window_end) range.
    - Mutates `scheduled_events` and `current_busy` if it finds a placement.

    Returns:
        (start_dt, end_dt) on success, or (None, None) if no fit is found.
    """
    needed = timedelta(minutes=chunk_minutes)

    # Use either the caller-supplied range or the global scheduling window
    local_ws = range_start or window_start
    local_we = range_end or window_end

    # Build free slots within the chosen range
    merged_busy = merge_busy_slots(current_busy)
    free_slots = invert_slots(merged_busy, local_ws, local_we)

    # Generate candidate windows based on event's date/time constraints
    candidates: List[Tuple[datetime, datetime]] = []
    for free_s, free_e in free_slots:
        for cand in generate_candidate_windows_for_event(event, free_s, free_e):
            candidates.append(cand)

    candidates.sort(key=lambda x: x[0])

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
            logger.info(
                "schedule_single_event: scheduled title=%r start=%s end=%s",
                new_ev["name"], start_dt, end_dt
            )

            # Update busy slots in-place so callers see the new state
            current_busy.append((start_dt, end_dt))
            merged = merge_busy_slots(current_busy)
            current_busy[:] = merged

            return start_dt, end_dt

    # No fit found
    return None, None

def schedule_events(
    event_requests_raw: List[dict],
    imported_events: List[dict],
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
    preferences: Optional[dict] = None,
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
    
    # Use preferred days/times if available
    blackout_days = convert_blackout_days(preferences) if preferences else []
    time_of_day_ranks = convert_time_of_day_rankings(preferences) if preferences else []

    # parse wake/bed times from preferences (expect ISO time string "HH:MM" or time object)
    wake_time = _parse_pref_time(preferences.get("wake_time")) if preferences else None
    bed_time  = _parse_pref_time(preferences.get("bed_time")) if preferences else None

    # determine local timezone to interpret time-of-day and wake/bed in user's local tz
    local_tz = _get_local_tz(preferences)

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
                for cand in generate_candidate_windows_for_event(event, free_s, free_e, wake_time=wake_time, bed_time=bed_time, local_tz=local_tz):
                    # Filter candidates based on preferred days
                    if not blackout_days:
                        candidates.append(cand)
                    elif cand[0].date().weekday() not in blackout_days:
                        candidates.append(cand)

            # If we have time-of-day preferences, score candidates by overlap with preferred windows for that candidate's day
            if time_of_day_ranks:
                candidates = score_and_sort_candidates(candidates, time_of_day_ranks, local_tz)
            else:
                # no time preferences -> keep chronological ordering
                candidates.sort(key=lambda x: x[0])

            needed = timedelta(minutes=chunk_minutes)
            logger.info("schedule_events: candidates=%s", candidates)
            for cand_s, cand_e in candidates:
                if (cand_e - cand_s) >= needed:
                    # Try to place inside preferred time-of-day subwindow if we have preferences
                    start_dt = None
                    end_dt = None
                    if time_of_day_ranks:
                        sub = find_preferred_subwindow(cand_s, cand_e, needed, time_of_day_ranks, wake_time=wake_time, bed_time=bed_time, local_tz=local_tz)
                        if sub:
                            start_dt, end_dt = sub
                    # Fallback: place at candidate start if no preferred subwindow fits
                    if start_dt is None:
                        # First, schedule this chunk anywhere in the global window
                        start_dt, end_dt = schedule_single_event(
                            event=event,
                            chunk_minutes=chunk_minutes,
                            current_busy=current_busy,
                            scheduled_events=scheduled_events,
                            window_start=window_start,
                            window_end=window_end,
                        )

                        if start_dt is None:
                            # Could not schedule this chunk at all
                            logger.warning(
                                "schedule_events: UNSCHEDULED title=%r minutes=%d (no fit)",
                                event.get("title"), chunk_minutes
                            )

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
                continue  # Move on to next chunk

            # Recurring weekly logic (try same time, then same day, then same week)
            if event.get("recurring") and event.get("recurring_until"):
                recurrence_end_date = event["recurring_until"]

                original_time = start_dt.time()
                occurrence_date = start_dt.date() + timedelta(weeks=1)

                while occurrence_date <= recurrence_end_date:

                    # Step 1: Try same time on same day
                    exact_start = to_datetime(occurrence_date, original_time)
                    exact_end = exact_start + timedelta(minutes=chunk_minutes)

                    conflict = any(
                        not (exact_end <= busy_s or exact_start >= busy_e)
                        for busy_s, busy_e in current_busy
                    )

                    if not conflict:
                        new_ev = {
                            "name": event.get("title"),
                            "description": event.get("description"),
                            "start": exact_start.isoformat(),
                            "end": exact_end.isoformat(),
                            "event_type": event.get("event_type"),
                            "priority": event.get("priority"),
                        }
                        scheduled_events.append(new_ev)
                        current_busy.append((exact_start, exact_end))
                        current_busy[:] = merge_busy_slots(current_busy)

                        logger.info("scheduled_events: recurring SAME TIME placement: %s", exact_start)
                        occurrence_date += timedelta(weeks=1)
                        continue

                    # Step 2: Try another time same day
                    day_start = to_datetime(occurrence_date, time.min)
                    day_end   = to_datetime(occurrence_date, time.max)

                    event_for_day = event.copy()
                    event_for_day["date_start"] = occurrence_date
                    event_for_day["date_end"]   = occurrence_date

                    r_start, r_end = schedule_single_event(
                        event=event_for_day,
                        chunk_minutes=chunk_minutes,
                        current_busy=current_busy,
                        scheduled_events=scheduled_events,
                        window_start=window_start,
                        window_end=window_end,
                        range_start=day_start,
                        range_end=day_end,
                    )

                    # Step 3: Try same week any time
                    if r_start is None:
                        week_end_date = occurrence_date + timedelta(days=6)
                        week_start_dt = day_start
                        week_end_dt   = to_datetime(week_end_date, time.max)

                        event_for_week = event.copy()
                        event_for_week["date_start"] = occurrence_date
                        event_for_week["date_end"]   = week_end_date

                        r_start, r_end = schedule_single_event(
                            event=event_for_week,
                            chunk_minutes=chunk_minutes,
                            current_busy=current_busy,
                            scheduled_events=scheduled_events,
                            window_start=window_start,
                            window_end=window_end,
                            range_start=week_start_dt,
                            range_end=week_end_dt,
                        )

                        if r_start is None:
                            logger.warning(
                                "schedule_events: recurring occurrence UNSCHEDULED "
                                "for title=%r in week starting %s",
                                event.get("title"), occurrence_date
                            )

                    occurrence_date += timedelta(weeks=1)
            # End of recurring logic
    logger.info("schedule_events: done scheduled=%d (incl. unscheduled placeholders=%d)",
                sum(1 for e in scheduled_events if e.get("start")), len(scheduled_events))  # LOG
    return scheduled_events