'''
Name: apps/scheduler/utils/scheduler.py
Description: Module for scheduling tasks
Authors: Hart Nurnberg, Audrey Pan, Kiara Grimsley, Ella Nguyen, Lauren D'Souza
Created: November 7, 2025
Last Modified: December 1, 2025
'''

from django.utils.timezone import make_aware, get_current_timezone, is_naive
from datetime import datetime, date, time, timedelta
from typing import List, Tuple, Dict, Optional
import copy
import pytz
from pytz import UTC
import logging
from .constants import PRIORITY_ORDER
import random
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
    Treat naive datetimes as server-local then convert to UTC.
    """
    logger.debug("_to_dt_utc: input=%r (type=%s)", x, type(x).__name__)
    if not x:
        logger.debug("_to_dt_utc: returning None (empty input)")
        return None
    if isinstance(x, datetime):
        if x.tzinfo:
            return x.astimezone(UTC)
        # naive -> assume server local
        local = make_aware(x, get_current_timezone())
        return local.astimezone(UTC)
    # ISO string from import_ics (e.g., '2025-11-08T14:30:00+00:00')
    dt = datetime.fromisoformat(str(x))
    if dt.tzinfo:
        return dt.astimezone(UTC)
    local = make_aware(dt, get_current_timezone())
    return local.astimezone(UTC)


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
		local_tz = get_current_timezone()
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
    candidates: List[Tuple[datetime, datetime]],
    preferences: dict = {},
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Schedule a single chunk of chunk_minutes minutes for event.
    - Looks for a free slot within provided candidates.
    - Tries to place in preferred time-of-day windows first (if candidates are scored).
    - Mutates `scheduled_events` and `current_busy` if it finds a placement.

    Returns:
        (start_dt, end_dt) on success, or (None, None) if no fit is found.
    """

    if preferences.get("randomize") and candidates:
        random.shuffle(candidates) # Randomize order of time chunk candidates (as opposed to chronological order)

    needed = timedelta(minutes=chunk_minutes)
    placed = False
    for cand_s, cand_e in candidates:
        if (cand_e - cand_s) < needed: # too small
            continue

        # Try to place in preferred subwindow
        start_dt = None
        end_dt = None
        if preferences.get("time_of_day_ranks"):
            sub = find_preferred_subwindow(
                cand_s, cand_e, needed,
                preferences.get("time_of_day_ranks"),
                wake_time=preferences.get("wake_time"),
                bed_time=preferences.get("bed_time"),
                local_tz=preferences.get("local_tz"),
            )

            if sub:
                start_dt, end_dt = sub
                placed = True

        # No preferred placement found, use candidate window directly
        if not placed:
            start_dt = cand_s
            end_dt = cand_s + needed

            # Check stay in candidate window
            if end_dt > cand_e:
                continue
            placed = True

        # Found placement, schedule it
        event_id = event.get("uid") if event.get("uid") is not None else event.get("id")
        if event_id is None:
            # Default ID: title_startTime
            event_id = f"{event.get('title')}_{start_dt.isoformat()}"

        new_ev = {
            "name": event.get("title"),
            "description": event.get("description"),
            "start": start_dt.isoformat(),  # tz-aware UTC
            "end": end_dt.isoformat(),      # tz-aware UTC
            "event_type": event.get("event_type"),
            "priority": event.get("priority"),
            "uid": event_id
        }

        # Add to scheduled events and update busy slots
        scheduled_events.append(new_ev)
        current_busy.append((start_dt, end_dt))
        current_busy[:] = merge_busy_slots(current_busy)

        logger.info(
            "schedule_events: scheduled title=%r start=%s end=%s",
            new_ev["name"], start_dt, end_dt
        )
        return start_dt, end_dt

    # No placement found
    logger.warning(
        "schedule_events: UNSCHEDULED title=%r minutes=%d (no fit)",
        event.get("title"), chunk_minutes
    )

    event_id = event.get("uid") or event.get("id")
    if event_id is None:
        event_id = f"{event.get('title')}_unscheduled_{chunk_minutes}min"

    scheduled_events.append({
        "name": event.get("title"),
        "description": event.get("description"),
        "start": None,
        "end": None,
        "event_type": event.get("event_type"),
        "priority": event.get("priority"),
        "unscheduled": True,
        "requested_minutes": chunk_minutes,
        "uid": event_id
    })
    return None, None

def schedule_events(
    event_requests_raw: List[dict],
    imported_events: List[dict],
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
    preferences: Optional[dict] = None,
    randomize: bool = False,
) -> List[Dict]:
    """
    Main scheduling routine.
    Inputs:
      - event_requests_raw: session event dicts (ISO strings) -> will be expanded
      - imported_events: output of import_ics (used to build busy slots)
      - window_start/window_end: overall scheduling timeframe (default: now .. +14 days)
      - randomize: if True, will shuffle candidate windows per event chunk so multiple
        runs can yield different schedules (still respecting constraints)
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
        window_end = window_start + timedelta(days=31)
    else:
        window_end = _to_dt_utc(window_end)

    # Build initial busy slots from imported (static) events
    busy = get_busy_from_imported(imported_events)
    current_busy = merge_busy_slots(busy[:])

    # Expand event requests, sort by priority/duration
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

    # Set up preference-based constraints
    # Use preferred days/times if available
    blackout_days = convert_blackout_days(preferences) if preferences else []
    time_of_day_ranks = convert_time_of_day_rankings(preferences) if preferences else []

    # parse wake/bed times from preferences (expect ISO time string "HH:MM" or time object)
    wake_time = _parse_pref_time(preferences.get("wake_time")) if preferences else None
    bed_time  = _parse_pref_time(preferences.get("bed_time")) if preferences else None

    # determine local timezone to interpret time-of-day and wake/bed in user's local tz
    local_tz = _get_local_tz(preferences)

    # Main scheduling loop
    for event in events_sorted:
        logger.info("schedule_events: placing event title=%r", event.get("title"))
        # Split event into chunks if needed
        chunks = split_into_chunks(event["duration_minutes"], event.get("split", False), event.get("split_minutes"))
        # Try to place each chunk of an event
        for chunk_minutes in chunks:
            # Build candidate windows for this event
            chunk_preferences = {
                "blackout_days": blackout_days,
                "time_of_day_ranks": time_of_day_ranks,
                "wake_time": wake_time,
                "bed_time": bed_time,
                "local_tz": local_tz,
                "randomize": randomize,
            }
            candidates = _form_candidates(current_busy, window_start, window_end, event, chunk_preferences)

            logger.debug("schedule_events: candidates=%s", candidates)

            # Try to place this chunk in one of the candidates
            start_time, end_time = schedule_single_event(event=event, chunk_minutes=chunk_minutes, current_busy=current_busy, scheduled_events=scheduled_events, candidates=candidates, preferences=chunk_preferences,)

            # Recurring weekly logic (try same time, then same day, then same week)
            if event.get("recurring") and event.get("recurring_until"):
                recurrence_end_date = event["recurring_until"]

                next_start_dt = start_time
                next_end_dt = end_time
                occurrence_date = next_start_dt.date() + timedelta(weeks=1)
                while occurrence_date <= recurrence_end_date:
                    # Step 1: Try same time on same day
                    time_start = next_start_dt.time()
                    time_end   = next_end_dt.time()
                    cand_start = to_datetime(occurrence_date, time_start, tzinfo_local=local_tz)
                    cand_end   = cand_start + timedelta(minutes=chunk_minutes)

                    event_for_day = event.copy()
                    event_for_day["date_start"] = occurrence_date
                    event_for_day["date_end"]   = occurrence_date
                    event_for_day["time_start"] = time_start
                    event_for_day["time_end"]   = time_end

                    candidates = _form_candidates(
                        busy_slots=current_busy,
                        window_start=cand_start,
                        window_end=cand_end,
                        event=event_for_day,
                        preferences=chunk_preferences,
                    )

                    r_start, _ = schedule_single_event(
                        event=event_for_day,
                        chunk_minutes=chunk_minutes,
                        current_busy=current_busy,
                        scheduled_events=scheduled_events,
                        candidates=candidates,
                        preferences=chunk_preferences,
                    )

                    # Step 2: Try another time same day
                    if r_start is None:
                        day_start = to_datetime(occurrence_date, time.min)
                        day_end   = to_datetime(occurrence_date, time.max)

                        event_for_day = event.copy()
                        event_for_day["date_start"] = occurrence_date
                        event_for_day["date_end"]   = occurrence_date

                        candidates = _form_candidates(
                            busy_slots=current_busy,
                            window_start=day_start,
                            window_end=day_end,
                            event=event_for_day,
                            preferences=chunk_preferences,
                        )

                        r_start, _ = schedule_single_event(
                            event=event_for_day,
                            chunk_minutes=chunk_minutes,
                            current_busy=current_busy,
                            scheduled_events=scheduled_events,
                            candidates=candidates,
                            preferences=chunk_preferences,
                        )

                    # Step 3: Try same week any time
                    if r_start is None:
                        # Split week: original occurrence_date +- 3 days
                        week_start_date = occurrence_date - timedelta(days=3)
                        week_end_date = occurrence_date + timedelta(days=3)
                        week_start = to_datetime(week_start_date, time.min)
                        week_end   = to_datetime(week_end_date, time.max)

                        event_for_week = event.copy()
                        event_for_week["date_start"] = week_start_date
                        event_for_week["date_end"]   = week_end_date

                        candidates = _form_candidates(
                            busy_slots=current_busy,
                            window_start=week_start,
                            window_end=week_end,
                            event=event_for_week,
                            preferences=chunk_preferences,
                        )

                        r_start, _ = schedule_single_event(
                            event=event_for_week,
                            chunk_minutes=chunk_minutes,
                            current_busy=current_busy,
                            scheduled_events=scheduled_events,
                            candidates=candidates,
                            preferences=chunk_preferences,
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


def _form_candidates(busy_slots, window_start, window_end, event, preferences):
    """
    Helper function to form candidate windows for an event within free slots.
    Takes busy slots, window start/end, event details, and user preferences.
    Returns a list of candidate (start, end) tuples.
    """
    local_tz = preferences.get("local_tz", get_current_timezone())

    # Convert dates → localized datetimes correctly
    if isinstance(window_start, date) and not isinstance(window_start, datetime):
        window_start = datetime.combine(window_start, time.min).replace(tzinfo=local_tz)
    else:
        window_start = window_start.astimezone(local_tz)

    if isinstance(window_end, date) and not isinstance(window_end, datetime):
        window_end = datetime.combine(window_end, time.max).replace(tzinfo=local_tz)
    else:
        window_end = window_end.astimezone(local_tz)

    # Normalize busy slots into the same tz
    busy_slots = [(s.astimezone(local_tz), e.astimezone(local_tz)) for s, e in busy_slots]

    # Compute free slots in local time
    free_slots = invert_slots(
        merge_busy_slots(busy_slots),
        window_start,
        window_end
    )

    candidates = []
    for free_s, free_e in free_slots:
        for cand in generate_candidate_windows_for_event(
            event,
            free_s,
            free_e,
            wake_time=preferences.get("wake_time"),
            bed_time=preferences.get("bed_time"),
            local_tz=local_tz
        ):
            if not preferences.get("blackout_days") or cand[0].date().weekday() not in preferences["blackout_days"]:
                candidates.append(cand)

    # Sort using local time
    if preferences.get("time_of_day_ranks"):
        candidates = score_and_sort_candidates(
            candidates,
            preferences["time_of_day_ranks"],
            local_tz
        )
    else:
        candidates.sort(key=lambda x: x[0])

    return candidates