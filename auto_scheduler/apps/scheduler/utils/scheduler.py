from datetime import datetime, date, time, timedelta
from typing import List, Tuple, Dict, Optional
import copy

# Simple data shapes used internally
# BusySlot = (start_datetime, end_datetime)
# TaskRequest = {
#   "title","description","duration_minutes","priority","event_type",
#   "date_start","date_end","time_start","time_end","split","split_minutes"
#   (date/time fields may be None or actual date/time objects)
# }
# ScheduledEvent = {"title","description","start","end","event_type","priority"}

def to_datetime(d: date, t: time) -> datetime:
    """Combine date + time into datetime; if time is None use midnight."""
    if t is None:
        return datetime.combine(d, time.min)
    return datetime.combine(d, t)

def merge_busy_slots(busy: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
    """Merge overlapping/adjacent busy intervals"""
    if not busy:
        return []
    busy_sorted = sorted(busy, key=lambda x: x[0])
    merged = []
    cur_s, cur_e = busy_sorted[0]
    for s, e in busy_sorted[1:]:
        if s <= cur_e + timedelta(seconds=1):
            # overlapping or adjacent
            cur_e = max(cur_e, e)
        else:
            merged.append((cur_s, cur_e))
            cur_s, cur_e = s, e
    merged.append((cur_s, cur_e))
    return merged

def invert_slots(busy: List[Tuple[datetime, datetime]], window_start: datetime, window_end: datetime) -> List[Tuple[datetime, datetime]]:
    """Return free slots inside [window_start, window_end) given merged busy intervals"""
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
    return free

def get_busy_from_imported(imported_events: List[dict]) -> List[Tuple[datetime, datetime]]:
    """
    Map whatever `import_ics` returned into list of (start, end) datetimes.
    Adapt this function to match your import_ics schema.
    """
    busy = []
    for ev in imported_events:
        # Example assumption: ev has 'start' and 'end' datetime objects already.
        s = ev.get("start")
        e = ev.get("end")
        if s and e:
            busy.append((s, e))
    return merge_busy_slots(busy)

def expand_task_request(raw_task: dict):
    """
    Convert ISO strings in task_requests to python date/time or None.
    The add_events view saved ISO strings for date/time.
    """
    t = copy.copy(raw_task)
    # date_start/date_end are YYYY-MM-DD or None
    if t.get("date_start"):
        t["date_start"] = date.fromisoformat(t["date_start"])
    if t.get("date_end"):
        t["date_end"] = date.fromisoformat(t["date_end"])
    # time_start/time_end are HH:MM:SS or None
    if t.get("time_start"):
        # forms.py used widget type="time", add_events isoformat for time -> "HH:MM:SS"
        t["time_start"] = time.fromisoformat(t["time_start"])
    if t.get("time_end"):
        t["time_end"] = time.fromisoformat(t["time_end"])
    # ensure ints
    t["duration_minutes"] = int(t.get("duration_minutes"))
    t["split_minutes"] = int(t["split_minutes"]) if t.get("split_minutes") else None
    t["split"] = bool(t.get("split"))
    return t

def generate_candidate_windows_for_task(task: dict, window_start: datetime, window_end: datetime) -> List[Tuple[datetime, datetime]]:
    """
    Given a task with optional date/time constraints, create candidate day/time windows where the task may be placed.
    Returns list of (slot_start_datetime, slot_end_datetime) where we can attempt to fit the task.
    Strategy:
      - If date_start/date_end present, iterate dates in that window; otherwise use overall window_start..window_end range.
      - For each day, clamp times to time_start/time_end if present.
    """
    ds = task.get("date_start")
    de = task.get("date_end")
    ts = task.get("time_start")
    te = task.get("time_end")

    results = []

    # Build date range to iterate
    start_date = ds if ds else window_start.date()
    end_date = de if de else window_end.date()

    # iterate inclusive by date
    d = start_date
    one_day = timedelta(days=1)
    while d <= end_date:
        day_start = datetime.combine(d, ts if ts else time.min)
        day_end   = datetime.combine(d, te if te else time.max)
        # clamp to global window
        slot_s = max(day_start, window_start)
        slot_e = min(day_end, window_end)
        if slot_s < slot_e:
            results.append((slot_s, slot_e))
        d = d + one_day
    return results

def split_into_chunks(duration_minutes: int, split: bool, split_minutes: Optional[int]) -> List[int]:
    """Return list of chunk durations (minutes). If split==False, returns [duration_minutes]."""
    if not split:
        return [duration_minutes]
    if not split_minutes:
        raise ValueError("split_minutes required when split is True")
    chunks = []
    remaining = duration_minutes
    while remaining > 0:
        chunk = min(split_minutes, remaining)
        chunks.append(chunk)
        remaining -= chunk
    return chunks

def schedule_tasks(
    task_requests_raw: List[dict],
    imported_events: List[dict],
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
) -> List[Dict]:
    """
    Main scheduling routine.
    Inputs:
      - task_requests_raw: session task dicts (ISO strings) -> will be expanded
      - imported_events: output of import_ics (used to build busy slots)
      - window_start/window_end: overall scheduling timeframe (default: now .. +14 days)
    Returns:
      - list of ScheduledEvent dicts: {"title","description","start","end","event_type","priority"}
    """

    if window_start is None:
        window_start = datetime.now()
    if window_end is None:
        window_end = window_start + timedelta(days=14)  # default two-week horizon

    busy = get_busy_from_imported(imported_events)
    # busy already merged
    free = invert_slots(busy, window_start, window_end)

    # Expand tasks and sort by priority+maybe duration (example: high -> medium -> low)
    priority_order = {"high": 0, "medium": 1, "low": 2}
    tasks = [expand_task_request(t) for t in task_requests_raw]
    tasks_sorted = sorted(tasks, key=lambda x: (priority_order.get(x.get("priority","medium"), 1), -int(x.get("duration_minutes",0))))

    scheduled_events = []
    # We'll maintain a mutable busy list that includes booked new events as we go
    current_busy = busy[:]
    current_busy = merge_busy_slots(current_busy)

    # helper: refresh free list from current_busy
    def compute_free():
        nonlocal current_busy
        return invert_slots(merge_busy_slots(current_busy), window_start, window_end)

    for task in tasks_sorted:
        chunks = split_into_chunks(task["duration_minutes"], task.get("split", False), task.get("split_minutes"))
        chunk_starts = []
        # For each chunk, attempt to place it in earliest fitting free slot that also sits inside allowed windows
        for chunk_minutes in chunks:
            placed = False
            free_slots = compute_free()
            # Candidate windows further restrict free slots per task constraints
            candidates = []
            for free_s, free_e in free_slots:
                # Intersect this free slot with task's allowed day/time windows
                for cand in generate_candidate_windows_for_task(task, free_s, free_e):
                    # candidate window already is within free slot because we passed free_s/free_e as window
                    candidates.append(cand)
            # Sort candidates by earliest start
            candidates = sorted(candidates, key=lambda x: x[0])
            needed = timedelta(minutes=chunk_minutes)
            for cand_s, cand_e in candidates:
                if (cand_e - cand_s) >= needed:
                    # schedule chunk at earliest possible start within candidate window
                    start_dt = cand_s
                    end_dt = start_dt + needed
                    # create scheduled event
                    new_ev = {
                        "title": task.get("title"),
                        "description": task.get("description"),
                        "start": start_dt,
                        "end": end_dt,
                        "event_type": task.get("event_type"),
                        "priority": task.get("priority"),
                    }
                    scheduled_events.append(new_ev)
                    # add to busy
                    current_busy.append((start_dt, end_dt))
                    current_busy = merge_busy_slots(current_busy)
                    placed = True
                    break
            if not placed:
                # could not place this chunk
                # current strategy: leave unscheduled (you could also return partial failure)
                # we mark the task chunk as unscheduled by adding None or logging
                scheduled_events.append({
                    "title": task.get("title"),
                    "description": task.get("description"),
                    "start": None,
                    "end": None,
                    "event_type": task.get("event_type"),
                    "priority": task.get("priority"),
                    "unscheduled": True,
                    "requested_minutes": chunk_minutes
                })
        # end chunks
    return scheduled_events
