'''
Name: apps/scheduler/views.py
Description: Views for handling scheduler functionality and the
                study preferences form.
Authors: Kiara Grimsley, Ella Nguyen, Audrey Pan, Reeny Huang
Created: October 26, 2025
Last Modified: November 19, 2025
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
import pytz
from .utils.constants import * # SESSION_*, LOGGER_NAME
from datetime import date
from apps.scheduler.utils.scheduler import preview_schedule_order

SESSION_IMPORTED_EVENTS = "imported_events" # parsed from ICS
SESSION_TASK_REQUESTS   = "task_requests" # user-entered tasks (requests)
from django.contrib import messages

logger = logging.getLogger(LOGGER_NAME)

UTC = pytz.UTC

@login_required
def upload_ics(request):
    '''
    Handle ICS file upload events.
    Renders upload form and processes uploaded files.
    '''

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
def add_events(request): # TODO: Ella + Hart
    '''
    View to add new events to a calendar after ICS upload.
    '''

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

    # Get scheduled events from session, or schedule if needed
    scheduled_events = request.session.get(SESSION_SCHEDULED_EVENTS, [])
    if not scheduled_events or request.session.get(SESSION_SCHEDULE_UPDATE, True):
        logger.info("view_calendar: reschedule needed; scheduling now")
        imported_events = request.session.get(SESSION_IMPORTED_EVENTS, [])
        event_requests = request.session.get(SESSION_EVENT_REQUESTS, [])

        # Schedule any events
        logger.info("view_calendar: scheduling %d events against %d imported events",
                    len(event_requests), len(imported_events))
        scheduled_events = imported_events + schedule_events(event_requests, imported_events)
        request.session[SESSION_SCHEDULED_EVENTS] = scheduled_events
        request.session[SESSION_SCHEDULE_UPDATE] = False # Reset update flag
        request.session.modified = True # Ensure session is saved

    logger.info("view_calendar: total events to display/export: %d", len(scheduled_events))

    # ICS Export
    if request.method == 'POST':
        action = request.POST.get("action", "export")

        # Delete Event
        if action == "delete":
            delete_type  = request.POST.get("delete_type")
            delete_index = request.POST.get("delete_index")

            try:
                idx = int(delete_index)
            except (TypeError, ValueError):
                idx = -1

            if delete_type == "imported":
                if 0 <= idx < len(imported_events):
                    logger.info("view_calendar: deleting imported event at index %d", idx)
                    imported_events.pop(idx)
                    request.session[SESSION_IMPORTED_EVENTS] = imported_events
            elif delete_type == "task":
                if 0 <= idx < len(event_requests):
                    logger.info("view_calendar: deleting task request at index %d", idx)
                    event_requests.pop(idx)
                    request.session[SESSION_TASK_REQUESTS] = event_requests

            # After deleting, redirect back to GET so refresh doesn't re-POST
            return redirect("scheduler:view_calendar")

        # Export ICS
        elif action == "export":
            # Use scheduler to find placement of task_requests
            logger.info("view_calendar: POST received; scheduling %d tasks against %d imported events",
                        len(task_requests), len(imported_events))
            scheduled_events = schedule_tasks(task_requests, imported_events)
            logger.info("view_calendar: scheduler returned %d events; exporting ICS", len(scheduled_events))
            events = imported_events + scheduled_events
            ics_stream = export_ics(events)
            resp = StreamingHttpResponse(ics_stream, content_type='text/calendar')
            resp['Content-Disposition'] = 'attachment; filename="ScheduledCalendar.ics"'
            logger.info("view_calendar: ICS response prepared (events_total=%d); returning download", len(events))
            # Possibly store scheduled events in session for later use??
            return resp
    
    preview = preview_schedule_order(task_requests)
    for i, t in enumerate(preview, start=1):
        t["schedule_order"] = i

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
        'events': events,
        'preview_tasks': preview,
        'imported_events': imported_events,
        'task_requests': task_requests
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