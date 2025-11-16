'''
Name: apps/scheduler/views.py
Description: Views for handling scheduler functionality and the
                study preferences form.
Authors: Kiara Grimsley, Ella Nguyen, Audrey Pan
Created: October 26, 2025
Last Modified: November 16, 2025
'''
import logging
from django.shortcuts import render, redirect
from django.core.files.storage import default_storage # Whatever our defined storage is
from django.urls import reverse
from django.http import StreamingHttpResponse
from .forms import ICSUploadForm, TaskForm, StudyPreferencesForm
from django.forms import formset_factory
from .utils.icsImportExport import import_ics, export_ics
from .utils.scheduler import schedule_tasks
from .utils.constants import * # SESSION_*, LOGGER_NAME

from django.contrib import messages

logger = logging.getLogger(LOGGER_NAME)

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

def add_events(request): # TODO: Ella + Hart
    '''
    View to add new events to a calendar after ICS upload.
    '''

    logger.info("Add Events view accessed for session=%s", request.session.session_key)

    TaskFormSet = formset_factory(TaskForm, extra=1, can_delete=False, max_num=30)

    if request.method == "POST":
        logger.info("add_events: binding TaskFormSet from POST data")
        formset = TaskFormSet(request.POST, prefix="tasks")
        logger.info("add_events: formset.is_valid? %s", formset.is_valid)

        if formset.is_valid():
            task_requests = []
            logger.info("add_events: processing %d forms", len(formset.cleaned_data))
            for form_data in formset.cleaned_data:
                if not form_data or form_data.get("DELETE"):
                    continue
                task_requests.append({
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
            logger.info("add_events: storing %d task requests to session", len(task_requests))
            request.session[SESSION_TASK_REQUESTS] = task_requests
            request.session[SESSION_SCHEDULE_UPDATE] = True # Mark schedule for update
            logger.info("add_events: redirecting to scheduler:view_calendar")
            # For MVP, we redirect to view/export page; scheduling engine can use these later.
            return redirect("scheduler:view_calendar")
    else:
        initial = request.session.get(SESSION_TASK_REQUESTS, [])
        logger.info("add_events: GET detected; preloading %d existing task requests", len(initial))
        formset = TaskFormSet(initial=initial, prefix="tasks")

    # Also pass a quick count of imported events for UX context
    imported_events = request.session.get(SESSION_IMPORTED_EVENTS, [])
    return render(
        request,
        "add_events.html",
        {"formset": formset, "imported_count": len(imported_events)}
    )

def view_calendar(request):
    logger.info("view_calendar: entered (method=%s, session_key=%s)",
                request.method, getattr(request.session, "session_key", None))

    scheduled_events = request.session.get(SESSION_SCHEDULED_EVENTS, [])
    if not scheduled_events or request.session.get(SESSION_SCHEDULE_UPDATE, True):
        logger.info("view_calendar: no scheduled events in session; scheduling now")
        imported_events = request.session.get(SESSION_IMPORTED_EVENTS, [])
        task_requests = request.session.get(SESSION_TASK_REQUESTS, [])

        # Schedule any tasks
        logger.info("view_calendar: scheduling %d tasks against %d imported events",
                    len(task_requests), len(imported_events))
        scheduled_events = imported_events + schedule_tasks(task_requests, imported_events)
        request.session[SESSION_SCHEDULED_EVENTS] = scheduled_events
        request.session[SESSION_SCHEDULE_UPDATE] = False # Reset update flag
        request.session.modified = True # Ensure session is saved


    logger.info("view_calendar: total events to display/export: %d", len(scheduled_events))



    if request.method == 'POST':
        ics_stream = export_ics(scheduled_events)
        resp = StreamingHttpResponse(ics_stream, content_type='text/calendar')
        resp['Content-Disposition'] = 'attachment; filename="ScheduledCalendar.ics"'
        logger.info("view_calendar: ICS response prepared (events_total=%d); returning download", len(scheduled_events))
        return resp

    # GET: just render the page
    logger.info("view_calendar: GET; rendering page with %d events", len(scheduled_events))
    return render(request, 'view_calendar.html', {'events': scheduled_events})

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