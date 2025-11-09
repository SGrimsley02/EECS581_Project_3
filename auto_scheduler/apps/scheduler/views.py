'''
Name: apps/scheduler/views.py
Description: Views for handling scheduler functionality.
Authors: Kiara Grimsley
Created: October 26, 2025
Last Modified: October 26, 2025
'''

from django.shortcuts import render, redirect
from django.core.files.storage import default_storage # Whatever our defined storage is
from django.urls import reverse
from django.http import StreamingHttpResponse, FileResponse, HttpResponse
from django.forms import formset_factory
from .forms import ICSUploadForm, TaskForm
from .utils.icsImportExport import import_ics, export_ics
from .utils.scheduler import schedule_tasks
from ics import Calendar, Event
import os
import time
import pytz

SESSION_IMPORTED_EVENTS = "imported_events" # parsed from ICS
SESSION_TASK_REQUESTS   = "task_requests" # user-entered tasks (requests)

UTC = pytz.UTC

def upload_ics(request):
    '''
    Handle ICS file upload events.
    Renders upload form and processes uploaded files.
    '''

    if request.method == 'POST': # POST request on form submission
        form = ICSUploadForm(request.POST, request.FILES)
        if form.is_valid(): # For now just if ics file exists
            ics_file = form.cleaned_data['ics_file']
            file_path = default_storage.save(ics_file.name, ics_file) # Save file to default storage
            events = import_ics(default_storage.path(file_path)) # Process the uploaded ICS file
            request.session['imported_events'] = events # Store events in session for later use
            request.session['uploaded_file_path'] = file_path # Store file path in session
            return redirect("scheduler:add_events") # Next page
    else:
        form = ICSUploadForm() # Empty form for GET request
    return render(request, 'upload_ics.html', {'form': form}) # Render

def add_events(request): # TODO: Ella + Hart
    '''
    View to add new events to a calendar after ICS upload.
    Exact form TBD.
    '''

    # TODO: Allow user to add events with details
        # Probably a FormSet of some sort that you can add in forms.py

    if request.method == 'POST': # On submission
        # TODO: Safely add the events to the database
            # Put logic to add events to DB as a utils/ model

        return redirect("scheduler:view_calendar") # Redirect to view + export page

    return render(request, 'add_events.html') # Render form to add events

def view_calendar(request): # TODO: Kiara
    '''
    View to display calendar events and allow ICS export.
    '''

    events = request.session.get('parsed_events', []) # Get events from session
    if not events: # If no events in session, error handling
        # Test events
        # events = import_ics('../../../data/sample2.ics')
        pass
        # TODO: Error handling for no events

    # TODO: Calendar view rendering

    # Test bypass
    request.method = 'POST'

    if request.method == 'POST': # On export request
        ics_file_stream = export_ics(events) # Export events to ICS format

        response = StreamingHttpResponse( # Download streaming
            ics_file_stream,
            content_type='text/calendar'
        )
        response['Content-Disposition'] = 'attachment; filename="SpaceCalendar.ics"'
        return response

    return render(request, 'view_calendar.html', {'events': events}) # Render calendar view

# VIEW CALENDAR METHOD STRICTLY JUST MADE FOR TESTING ADD EVENT
def view_calendar(request):
    events = request.session.get('imported_events', [])

    if request.method == 'POST':
        ics_stream = export_ics(events)
        resp = StreamingHttpResponse(ics_stream, content_type='text/calendar')
        resp['Content-Disposition'] = 'attachment; filename="SpaceCalendar.ics"'
        return resp

    # GET: just render the page
    return render(request, 'view_calendar.html', {'events': events})

def run_scheduler_and_export(request):
    """
    Run the scheduler using session data and produce a new ICS file (a copy of uploaded ICS with new events).
    Expected in session:
      - 'imported_events' : list (from import_ics) where each event has ISO start/end strings
      - 'task_requests'   : list (from add_events formset)
      - 'uploaded_file_path': path (relative) where uploaded ICS was saved (used with default_storage)
    This view writes a new ICS file under scheduled_exports/<original_basename>_scheduled_<ts>.ics
    and stores that relative path in session['scheduled_file_path'].
    """
    # only allow POST to trigger scheduling (safer); if GET, redirect back
    if request.method != "POST":
        return redirect("scheduler:view_calendar")

    SESSION_IMPORTED_EVENTS = "imported_events"
    SESSION_TASK_REQUESTS = "task_requests"

    imported_events = request.session.get(SESSION_IMPORTED_EVENTS)
    task_requests = request.session.get(SESSION_TASK_REQUESTS)
    uploaded_file_path = request.session.get('uploaded_file_path')

    if not imported_events or not uploaded_file_path:
        return HttpResponse("No uploaded calendar found. Upload an .ics first.", status=400)
    if not task_requests:
        return HttpResponse("No tasks to schedule. Add tasks first.", status=400)

    # Run the scheduler -> returns list of dicts with start/end as timezone-aware datetimes or None
    scheduled_events = schedule_tasks(task_requests, imported_events)

    # Prepare output relative path and ensure dir
    base_name = os.path.splitext(os.path.basename(uploaded_file_path))[0]
    ts = int(time.time())
    out_rel = os.path.join("scheduled_exports", f"{base_name}_scheduled_{ts}.ics")

    # Read original ICS content from storage (works for local or remote backends)
    try:
        with default_storage.open(uploaded_file_path, "r") as fh:
            original_text = fh.read()
    except Exception as e:
        # If unable to open, abort
        return HttpResponse(f"Failed to read uploaded ICS file: {e}", status=500)

    # Parse original calendar into ics.Calendar
    try:
        cal = Calendar(original_text)
    except Exception:
        # If parsing fails, create an empty calendar to add scheduled events to
        cal = Calendar()

    # Add scheduled events to the calendar (skip unscheduled entries)
    for ev in scheduled_events:
        if not ev.get("start") or not ev.get("end"):
            continue
        e = Event()
        e.name = ev.get("title") or ev.get("name") or "No Title"
        # ensure tz-aware datetimes; scheduler returns tz-aware UTC in our utils
        start_dt = ev.get("start")
        end_dt = ev.get("end")
        # ics.Event accepts tz-aware datetimes; set to UTC if naive
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=UTC)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=UTC)
        e.begin = start_dt
        e.end = end_dt
        e.description = ev.get("description") or ""
        # optionally attach metadata to description
        meta = []
        if ev.get("event_type"):
            meta.append(f"Type: {ev.get('event_type')}")
        if ev.get("priority"):
            meta.append(f"Priority: {ev.get('priority')}")
        if meta:
            e.description = (e.description or "") + ("\n\n" + " | ".join(meta))
        cal.events.add(e)

    # Write combined calendar to storage (use text mode)
    # default_storage.open(out_rel, "w") returns a file-like object we can write strings to
    try:
        # ensure directory exists when using filesystem-backed storage
        try:
            abs_out = default_storage.path(out_rel)
            os.makedirs(os.path.dirname(abs_out), exist_ok=True)
        except Exception:
            # storage backend doesn't expose .path (S3 etc.) — ignore
            pass

        with default_storage.open(out_rel, "w") as outfh:
            outfh.write("".join(cal.serialize_iter()))
    except Exception as e:
        return HttpResponse(f"Failed to write scheduled ICS file: {e}", status=500)

    # Store scheduled file path & scheduled_events (serialized) in session for UI
    request.session['scheduled_file_path'] = out_rel

    # Convert scheduled_events to JSON-serializable form (ISO strings)
    serializable = []
    for ev in scheduled_events:
        s = ev.get("start").astimezone(UTC).isoformat() if ev.get("start") else None
        e = ev.get("end").astimezone(UTC).isoformat() if ev.get("end") else None
        serializable.append({
            "title": ev.get("title"),
            "description": ev.get("description"),
            "start": s,
            "end": e,
            "event_type": ev.get("event_type"),
            "priority": ev.get("priority"),
            "unscheduled": ev.get("unscheduled", False),
            "requested_minutes": ev.get("requested_minutes")
        })
    request.session['scheduled_events'] = serializable

    # Redirect to calendar view where user can inspect results & download
    return redirect("scheduler:view_calendar")


def download_scheduled_ics(request):
    """
    Stream the scheduled .ics file stored in session['scheduled_file_path'] to the browser.
    """
    p = request.session.get('scheduled_file_path')
    if not p:
        return HttpResponse("No scheduled file available.", status=404)
    try:
        fh = default_storage.open(p, "rb")
        # filename for download should be base name
        filename = os.path.basename(p)
        return FileResponse(fh, as_attachment=True, filename=filename)
    except Exception as e:
        return HttpResponse(f"Failed to open scheduled file: {e}", status=500)