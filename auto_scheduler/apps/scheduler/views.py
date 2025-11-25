'''
Name: apps/scheduler/views.py
Description: Views for handling scheduler functionality and the
                study preferences form.
Authors: Kiara Grimsley, Ella Nguyen, Audrey Pan, Reeny Huang, Hart Nurnberg
Created: October 26, 2025
Last Modified: November 22, 2025
'''
import logging

from django.shortcuts import render, redirect
from django.core.files.storage import default_storage # Whatever our defined storage is
from django.urls import reverse
from django.http import StreamingHttpResponse, JsonResponse
from django.conf import settings
from django.forms import formset_factory
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required

from .forms import ICSUploadForm, EventForm, StudyPreferencesForm

from .utils.icsImportExport import import_ics, export_ics
from .utils.scheduler import schedule_events
from .utils.stats import compute_time_by_event_type
from .models import Calendar
from .models import EventType as EventTypeModel

import pytz
from .utils.constants import * # SESSION_*, LOGGER_NAME
from .utils.constants import EventType
from datetime import date, timedelta, datetime
from apps.scheduler.utils.scheduler import preview_schedule_order
import copy
import json

from django.contrib import messages

logger = logging.getLogger(LOGGER_NAME)

UTC = pytz.UTC

# ============================================================
#  VIEWS
# ============================================================

@login_required
def home(request):
    '''
    Home view that redirects to preferences.
    '''
    return redirect('scheduler:preferences')

def auth_view(request):
    '''
    View for handling user authentication (signup).
    Renders signup forms and processes authentication.
    '''
    if request.method == 'POST':
        form = UserCreationForm(request.POST or None)
        if form.is_valid():
            form.save()
            messages.success(request, "Account created successfully. Please log in.")
            logger.info("New user account created.")
            return redirect('scheduler:login')
        else:
            logger.warning("Signup form invalid: %s", form.errors)
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})

@login_required
def upload_ics(request):
    '''
    Handle ICS file upload events.
    Renders upload form and processes uploaded files.
    '''
    # Show recap banner if preferences haven't been updated in a while
    check_preferences_recap(request)

    if request.method == 'POST': # POST request on form submission
        form = ICSUploadForm(request.POST, request.FILES)
        if form.is_valid(): # For now just if ics file exists
            ics_file = form.cleaned_data['ics_file']
            try:
                file_path = default_storage.save(ics_file.name, ics_file) # Save file to default storage
                events = import_ics(default_storage.path(file_path)) # Process the uploaded ICS file
                request.session[SESSION_IMPORTED_EVENTS] = events # Store events in session for later use
                request.session[SESSION_FILE_PATH] = file_path # Store file path in session
                request.session[SESSION_SCHEDULE_UPDATE] = True # Mark schedule for update
                messages.success(request, "Calendar imported")
                logger.info("ICS import success: file=%s events=%s", ics_file.name, len(events))
                return redirect("scheduler:add_events") # Next page
            except Exception as e:
                logger.exception("ICS import failed")
                messages.error(request, "We couldn't read that .ics file. Please verify the file and try again.")
        else:
            logger.warning("ICS upload form invalid: %s", form.errors)
    else:
        form = ICSUploadForm() # Empty form for GET request
    return render(request, 'upload_ics.html', {'form': form}) # Render

@login_required
def add_events(request):
    '''
    View to add new events to a calendar after ICS upload.
    '''
    # Show recap banner if preferences haven't been updated in a while
    check_preferences_recap(request)

    logger.info("Add Events view accessed for session=%s", request.session.session_key)

    EventFormSet = formset_factory(EventForm, extra=1, can_delete=False, max_num=30)

    if request.method == "POST":
        logger.info("add_events: binding EventFormSet from POST data")
        formset = EventFormSet(request.POST, prefix="events")
        logger.info("add_events: formset.is_valid? %s", formset.is_valid)

        if formset.is_valid():
            event_requests = []
            logger.info("add_events: processing %d forms", len(formset.cleaned_data))
            for form_data in formset.cleaned_data:
                if not form_data or form_data.get("DELETE"):
                    continue
                event_requests.append({
                    "title": form_data["title"],
                    "description": form_data.get("description", ""),
                    "duration_minutes": form_data["duration_minutes"],
                    "priority": form_data["priority"],
                    "event_type": form_data["event_type"],
                    # Optional constraints (may be None)
                    "date_start": form_data.get("date_start").isoformat() if form_data.get("date_start") else None,
                    "date_end":   form_data.get("date_end").isoformat()   if form_data.get("date_end")   else None,
                    "time_start": form_data.get("time_start").isoformat() if form_data.get("time_start") else None,
                    "time_end":   form_data.get("time_end").isoformat()   if form_data.get("time_end")   else None,
                    "split": form_data.get("split") or False,
                    "split_minutes": form_data.get("split_minutes"),
                    "recurring": form_data.get("recurring") or False,
                    "recurring_until": form_data.get("recurring_until").isoformat()
                        if form_data.get("recurring_until") else None,
                })
            logger.info("add_events: storing %d event requests to session", len(event_requests))
            request.session[SESSION_EVENT_REQUESTS] = event_requests
            request.session[SESSION_SCHEDULE_UPDATE] = True # Mark schedule for update
            logger.info("add_events: redirecting to scheduler:view_calendar")
            # For MVP, we redirect to view/export page; scheduling engine can use these later.
            return redirect("scheduler:view_calendar")
    else:
        initial = request.session.get(SESSION_EVENT_REQUESTS, [])
        logger.info("add_events: GET detected; preloading %d existing event requests", len(initial))
        formset = EventFormSet(initial=initial, prefix="events")

    # Also pass a quick count of imported events for UX context
    imported_events = request.session.get(SESSION_IMPORTED_EVENTS, [])
    return render(
        request,
        "add_events.html",
        {"formset": formset, "imported_count": len(imported_events)}
    )

@login_required
def view_calendar(request):
    logger.info("view_calendar: entered (method=%s, session_key=%s)",
                request.method, getattr(request.session, "session_key", None))

    # Show recap banner if preferences haven't been updated in a while
    check_preferences_recap(request)

    # Get scheduled events from session, or schedule if needed
    scheduled_events = request.session.get(SESSION_SCHEDULED_EVENTS, [])
    if not scheduled_events or request.session.get(SESSION_SCHEDULE_UPDATE, True):
        logger.info("view_calendar: reschedule needed; scheduling now")
        # Get imported events from DB + session
        calendar = request.user.calendars.first()
        db_events = _db_events_to_session(calendar) if calendar else []
        logger.debug("Found DB events: %d", len(db_events))
        session_events = request.session.get(SESSION_IMPORTED_EVENTS, [])

        # TODO: Improve deduplication logic, extremely rudimentary rn
        seen = set()
        imported_events = []
        for ev in session_events: # Deduplicate, prefer session (live) events
            uid = ev.get("uid") or ev.get("id")
            if uid:
                seen.add(uid)
            title = ev.get("title") or ev.get("name")
            start = ev.get("start") or ev.get("start_time")
            title_key = (title, start)
            seen.add(title_key) # uid is strong key, this is weak key

            if uid not in seen and title_key not in seen:
                imported_events.append(ev)
        for ev in db_events: # Deduplicate, db_events come second
            uid = ev.get("uid") or ev.get("id")
            title = ev.get("title") or ev.get("name")
            start = ev.get("start") or ev.get("start_time")
            title_key = (title, start)
            if uid not in seen and title_key not in seen:
                imported_events.append(ev)

        event_requests = request.session.get(SESSION_EVENT_REQUESTS, [])

        # Get preferences for scheduling
        preferences = request.session.get(SESSION_PREFERENCES, {})

        # Schedule any events
        logger.info("view_calendar: scheduling %d events against %d imported events",
                    len(event_requests), len(imported_events))
        scheduled_events = imported_events + schedule_events(event_requests, imported_events, preferences=preferences)
        request.session[SESSION_SCHEDULED_EVENTS] = scheduled_events
        request.session[SESSION_IMPORTED_EVENTS] = None # Clear imported events
        request.session[SESSION_EVENT_REQUESTS] = None # Clear event requests
        request.session[SESSION_SCHEDULE_UPDATE] = False # Reset update flag
        request.session.modified = True # Ensure session is saved

    logger.info("view_calendar: total events to display/export: %d", len(scheduled_events))

    # ICS Export
    if request.method == 'POST':
        action = request.POST.get("action", "export")

        # Edit event
        if action == "edit":
            # snapshot for undo
            _push_undo(request)

            edit_type = request.POST.get("edit_type")
            edit_index = request.POST.get("edit_index")
            try:
                idx = int(edit_index)
            except (TypeError, ValueError):
                idx = -1

            # fields submitted from the form
            new_title = request.POST.get("new_title", "").strip()
            new_description = request.POST.get("new_description", "").strip()
            new_event_type = request.POST.get("new_event_type", "").strip()

            imported_events = request.session.get(SESSION_IMPORTED_EVENTS, [])
            event_requests = request.session.get(SESSION_EVENT_REQUESTS, [])

            if edit_type == "imported" and 0 <= idx < len(imported_events):
                logger.info("view_calendar: editing imported event at index %d", idx)
                ev = imported_events[idx]
                if new_title:
                    # update common keys used elsewhere
                    ev["name"] = new_title
                    ev["title"] = new_title
                # allow clearing description if empty string provided
                if new_description:
                    ev["description"] = new_description
                else:
                    ev.pop("description", None)
                if new_event_type:
                    ev["event_type"] = new_event_type
                else:
                    ev.pop("event_type", None)

                imported_events[idx] = ev
                request.session[SESSION_IMPORTED_EVENTS] = imported_events

            elif edit_type == "task" and 0 <= idx < len(event_requests):
                logger.info("view_calendar: editing task request at index %d", idx)
                t = event_requests[idx]
                if new_title:
                    t["title"] = new_title
                if new_description:
                    t["description"] = new_description
                else:
                    t.pop("description", None)
                if new_event_type:
                    t["event_type"] = new_event_type
                else:
                    t.pop("event_type", None)

                event_requests[idx] = t
                request.session[SESSION_EVENT_REQUESTS] = event_requests

            # mark schedule stale and persist session
            request.session[SESSION_SCHEDULE_UPDATE] = True
            request.session.pop(SESSION_SCHEDULED_EVENTS, None)
            request.session.modified = True

            return redirect("scheduler:view_calendar")

        # Delete Event
        if action == "delete":
            _push_undo(request)  # snapshot before the change

            delete_type  = request.POST.get("delete_type")
            delete_index = request.POST.get("delete_index")

            try:
                idx = int(delete_index)
            except (TypeError, ValueError):
                idx = -1

            imported_events = request.session.get(SESSION_IMPORTED_EVENTS, [])
            event_requests   = request.session.get(SESSION_EVENT_REQUESTS, [])

            if delete_type == "imported" and 0 <= idx < len(imported_events):
                logger.info("view_calendar: deleting imported event at index %d", idx)
                imported_events.pop(idx)
                request.session[SESSION_IMPORTED_EVENTS] = imported_events
            elif delete_type == "task" and 0 <= idx < len(event_requests):
                logger.info("view_calendar: deleting task request at index %d", idx)
                event_requests.pop(idx)
                request.session[SESSION_EVENT_REQUESTS] = event_requests

            request.session.modified = True
            request.session[SESSION_SCHEDULE_UPDATE] = True
            request.session.pop(SESSION_SCHEDULED_EVENTS, None)
            return redirect("scheduler:view_calendar")

        # Undo
        elif action == "undo":
            undo_stack = request.session.get(SESSION_UNDO_STACK, [])
            redo_stack = request.session.get(SESSION_REDO_STACK, [])

            if undo_stack:
                logger.info("view_calendar: undo requested")
                # push current to redo, restore last undo
                redo_stack.append(_get_current_state(request))
                prev_state = undo_stack.pop()
                request.session[SESSION_UNDO_STACK] = undo_stack
                request.session[SESSION_REDO_STACK] = redo_stack
                _apply_state(request, prev_state)

            return redirect("scheduler:view_calendar")

        # REDO
        elif action == "redo":
            undo_stack = request.session.get(SESSION_UNDO_STACK, [])
            redo_stack = request.session.get(SESSION_REDO_STACK, [])

            if redo_stack:
                logger.info("view_calendar: redo requested")
                # push current to undo, restore last redo
                undo_stack.append(_get_current_state(request))
                next_state = redo_stack.pop()
                request.session[SESSION_UNDO_STACK] = undo_stack
                request.session[SESSION_REDO_STACK] = redo_stack
                _apply_state(request, next_state)

            return redirect("scheduler:view_calendar")

        # Export ICS
        elif action == "export":
            logger.info("view_calendar: export ICS requested with %d events", len(scheduled_events))
            # Export to DB
            calendar = request.user.calendars.first()
            if not calendar: # If no calendar yet, create one
                calendar = Calendar.objects.create(
                    owner=request.user,
                    name="Default",
                    description="Auto-created calendar"
                )
            _save_scheduled_events_to_db(scheduled_events, calendar)
            # Export to ICS
            ics_stream = export_ics(scheduled_events)
            resp = StreamingHttpResponse(ics_stream, content_type='text/calendar')
            resp['Content-Disposition'] = 'attachment; filename="ScheduledCalendar.ics"'
            return resp

    # GET: recompute latest lists & preview



    # flags for template (to disable buttons)
    undo_available = bool(request.session.get(SESSION_UNDO_STACK))
    redo_available = bool(request.session.get(SESSION_REDO_STACK))

    # Determine month/year to show
    month = request.GET.get('month')
    year = request.GET.get('year')
    if not month or not year:
        today = date.today()
        month = today.month
        year = today.year
    else:
        month = int(month)
        year = int(year)

    # Render context
    ctx = {
        'DEBUG': settings.DEBUG,
        'debug_events': scheduled_events,
        'initial_date': f"{year:04d}-{month:02d}-01",
        'events': scheduled_events,
        'preview_tasks': None,
        'imported_events': None,
        'event_requests': None,
        'undo_available': undo_available,
        'redo_available': redo_available,
        'event_type_choices': EventType.values,
    }
    logger.info("view_calendar: GET; rendering page with %d events", len(scheduled_events))
    return render(request, 'view_calendar.html', ctx)

def event_feed(request):
    '''
    Provides scheduled events in JSON format for FullCalendar.
    Gets rendered by view_calendar template.
    '''
    scheduled_events = request.session.get(SESSION_SCHEDULED_EVENTS, [])

    # Convert your stored events into FullCalendar format
    formatted = []
    for ev in scheduled_events:
        formatted.append({
            "id": ev.get("id", None) or ev.get("uid", None),
            "title": ev.get("name") or ev.get("title") or "(No Title)",
            "start": ev.get("start"),
            "end": ev.get("end"),
            "allDay": False,
            "className": [f"etype-{ev.get('event_type', 'other').lower().replace(' ', '-')}"] if ev.get("event_type") else [],
            "extendedProps": ev,  # keep all original data
        })

    return JsonResponse(formatted, safe=False)

@login_required
def preferences(request):
    """
    Create/update study preferences. Stores selections in session (JSON-safe).
    Shows a success message on save.
    """
    # Pull previously saved preferences (if any) from the session
    initial = request.session.get(SESSION_PREFERENCES, None)

    if request.method == 'POST':
        # Bind submitted from values
        form = StudyPreferencesForm(request.POST)

        if form.is_valid():
            # Copy values so we can modify them safely
            cleaned = form.cleaned_data.copy()

            # Make TimeField values JSON-safe, so convert them to strs that are safe
            for key in ('wake_time', 'bed_time'):
                if cleaned.get(key):
                    cleaned[key] = cleaned[key].strftime('%H:%M')

            # Store updated preferences in the session
            request.session[SESSION_PREFERENCES] = cleaned
            request.session[SESSION_SCHEDULE_UPDATE] = True # Mark schedule for update

            # Remember when preferences were last updated (for recap prompt)
            request.session[SESSION_PREF_LAST_UPDATED] = date.today().isoformat()
            # user just updated prefs → reminder should be allowed again in the future
            request.session[SESSION_PREF_RECAP_DISMISSED] = False
            request.session.modified = True

            # Show success banner on the next load
            messages.add_message(request, messages.INFO, "Preferences saved.", extra_tags="prefs-bold-red")
            logger.info("Preferences updated in session for anon/session=%s", request.session.session_key)

            # Redirect to avoid resubmission on refresh
            return redirect('scheduler:preferences')
        else:
            logger.warning("Preferences form invalid", form.errors)
    else:
        # GET request, show the form prefilled with saved values (if any)
        form = StudyPreferencesForm(initial=initial)

    # Render the page with the form
    return render(request, 'preferences.html', {'form': form})

@login_required
def dismiss_preferences_recap(request):
    """
    Allow user to dismiss the study-preferences recap reminder
    until the next time they update their preferences.
    """
    request.session[SESSION_PREF_RECAP_DISMISSED] = True
    request.session.modified = True

    # Redirect back to the previous page if possible
    next_url = request.GET.get("next") or "scheduler:upload_ics"
    return redirect(next_url)

@login_required
def event_stats(request):
    """
    Display basic statistics for the user's scheduled events.
    Initial focus: total time spent per event_type, with a chart.
    """
    check_preferences_recap(request)

    scheduled_events = request.session.get(SESSION_SCHEDULED_EVENTS, [])

    # If no events at all, show empty state but still include filter fields
    start_str = request.GET.get("start", "")
    end_str = request.GET.get("end", "")

    if not scheduled_events:
        return render(request, "event_stats.html", {
            "has_data": False,
            "type_stats": [],
            "labels_json": "[]",
            "minutes_json": "[]",
            "start_date": start_str,
            "end_date": end_str,
        })

    # Parse date filters safely
    start_date = None
    end_date = None

    try:
        if start_str:
            start_date = datetime.fromisoformat(start_str).date()
        if end_str:
            end_date = datetime.fromisoformat(end_str).date()
    except ValueError:
        start_date = None
        end_date = None

    # Filtering
    if start_date or end_date:
        scheduled_events = [
            ev for ev in scheduled_events
            if _event_in_range(ev, start_date, end_date)
        ]

    # After filtering, if nothing matched:
    if not scheduled_events:
        return render(request, "event_stats.html", {
            "has_data": False,
            "type_stats": [],
            "labels_json": "[]",
            "minutes_json": "[]",
            "start_date": start_str,
            "end_date": end_str,
        })

    # Compute time-per-event-type stats
    type_stats = compute_time_by_event_type(scheduled_events)
    labels = [row["event_type"] for row in type_stats]
    minutes = [row["minutes"] for row in type_stats]

    # Return full context (your previous version forgot start/end here)
    return render(request, "event_stats.html", {
        "has_data": True,
        "type_stats": type_stats,
        "labels_json": json.dumps(labels),
        "minutes_json": json.dumps(minutes),
        "start_date": start_str,
        "end_date": end_str,
    })

# ============================================================
#  HANDLERS
# ============================================================

def delete_event(request, event_id):
    print("delete_event: ENTERED", request.method, request.session.session_key, event_id)
    if request.method == 'POST':
        if event_id is not None:
            _push_undo(request)  # snapshot before the change

            scheduled_events = request.session.get(SESSION_SCHEDULED_EVENTS, [])
            updated_events = [ev for ev in scheduled_events if str(ev.get("uid")) != str(event_id)]
            request.session[SESSION_SCHEDULED_EVENTS] = updated_events
            request.session.modified = True

            return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'failed'}, status=400)


# ============================================================
#  MESSAGE
# ============================================================

def check_preferences_recap(request):
    """
    Add a recap reminder message if the user's study preferences
    haven't been updated in PREFERENCES_RECAP_DAYS and they haven't dismissed it.
    """
    if request.session.get(SESSION_PREF_RECAP_DISMISSED):
        return

    last_pref_str = request.session.get(SESSION_PREF_LAST_UPDATED)
    if not last_pref_str:
        # missing --> treat as very old date
        last_pref_date = date.min
        request.session[SESSION_PREF_LAST_UPDATED] = last_pref_date.isoformat()
        request.session.modified = True
    else:
        try:
            last_pref_date = date.fromisoformat(last_pref_str)
        except ValueError:
            # If something weird is stored, fall back to "very old"
            last_pref_date = date.min
            request.session[SESSION_PREF_LAST_UPDATED] = last_pref_date.isoformat()
            request.session.modified = True

    if date.today() - last_pref_date >= timedelta(days=PREFERENCES_RECAP_DAYS):
        messages.info(
            request,
            "It's been a while since you updated your study preferences. "
            "You can review them on the Preferences page.",
            extra_tags="prefs-recap",
        )

# ============================================================
#  HELPERS
# ============================================================

def _get_current_state(request):
    return {
        "imported_events": copy.deepcopy(
            request.session.get(SESSION_IMPORTED_EVENTS, [])
        ),
        "event_requests": copy.deepcopy(
            request.session.get(SESSION_EVENT_REQUESTS, [])
        ),
    }

def _apply_state(request, state):
    request.session[SESSION_IMPORTED_EVENTS] = state.get("imported_events", [])
    request.session[SESSION_EVENT_REQUESTS] = state.get("event_requests", [])
    request.session[SESSION_SCHEDULE_UPDATE] = True
    request.session.pop(SESSION_SCHEDULED_EVENTS, None)
    request.session.modified = True

def _push_undo(request):
    undo_stack = request.session.get(SESSION_UNDO_STACK, [])
    undo_stack.append(_get_current_state(request))
    # cap history to last N steps
    if len(undo_stack) > 20:
        undo_stack.pop(0)
    request.session[SESSION_UNDO_STACK] = undo_stack
    # any new edit clears redo history
    request.session[SESSION_REDO_STACK] = []
    request.session.modified = True

def _event_in_range(ev, start_date, end_date):
    ev_start = datetime.fromisoformat(ev["start"]).date()
    if start_date and ev_start < start_date:
        return False
    if end_date and ev_start > end_date:
        return False
    return True

def _db_events_to_session(calendar):
    """Convert DB events into the dict format used by the scheduler/session."""
    events = []
    for ev in calendar.events.all():
        events.append({
            "uid": str(ev.id),
            "title": ev.summary,
            "name": ev.summary,
            "description": ev.description or "",
            "start": ev.start_time.isoformat(),
            "end": ev.end_time.isoformat(),
            "event_type": ev.event_type.name if ev.event_type else None,
            "location": ev.location,
            "alarm": ev.alarm,
        })
    return events

def _save_scheduled_events_to_db(all_events, calendar):
    """
    Saves FINAL scheduled events (imported + scheduled tasks) into DB.
    Clears the old calendar contents first to ensure no duplicates.
    """
    calendar.clear_events()

    for ev in all_events:
        start = datetime.fromisoformat(ev["start"])
        end = datetime.fromisoformat(ev["end"])
        event_type = ev.get("event_type") # Convert to EventType instance
        event_type = EventTypeModel.objects.filter(name=event_type).first() if event_type else None
        calendar.create_event(
            summary=ev.get("title") or ev.get("name") or "(No Title)",
            start_time=start,
            end_time=end,
            event_type=event_type,
            description=ev.get("description", ""),
            location=ev.get("location"),
            alarm=ev.get("alarm", False),
        )