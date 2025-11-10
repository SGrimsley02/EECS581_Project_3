'''
Name: apps/scheduler/views.py
Description: Views for handling scheduler functionality.
Authors: Kiara Grimsley, Ella Nguyen, Hart Nurnberg
Created: October 26, 2025
Last Modified: November 8, 2025
'''

from django.shortcuts import render, redirect
from django.core.files.storage import default_storage # Whatever our defined storage is
from django.urls import reverse
from django.http import StreamingHttpResponse
from django.forms import formset_factory
from .forms import ICSUploadForm, TaskForm
from .utils.icsImportExport import import_ics, export_ics
from .utils.scheduler import schedule_tasks
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

    TaskFormSet = formset_factory(TaskForm, extra=1, can_delete=False, max_num=30)

    if request.method == "POST":
        formset = TaskFormSet(request.POST, prefix="tasks")
        if formset.is_valid():
            task_requests = []
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
            request.session[SESSION_TASK_REQUESTS] = task_requests
            # For MVP, we redirect to view/export page; scheduling engine can use these later.
            return redirect("scheduler:view_calendar")
    else:
        initial = request.session.get(SESSION_TASK_REQUESTS, [])
        formset = TaskFormSet(initial=initial, prefix="tasks")

    # Also pass a quick count of imported events for UX context
    imported_events = request.session.get(SESSION_IMPORTED_EVENTS, [])
    return render(
        request,
        "add_events.html",
        {"formset": formset, "imported_count": len(imported_events)}
    )

def view_calendar(request):
    imported_events = request.session.get(SESSION_IMPORTED_EVENTS, [])
    task_requests = request.session.get(SESSION_TASK_REQUESTS, [])

    events = imported_events + task_requests

    if request.method == 'POST':
        # Use scheduler to find placement of task_requests
        scheduled_events = schedule_tasks(task_requests, imported_events)
        events = imported_events + scheduled_events
        ics_stream = export_ics(events)
        resp = StreamingHttpResponse(ics_stream, content_type='text/calendar')
        resp['Content-Disposition'] = 'attachment; filename="ScheduledCalendar.ics"'
        # Possibly store scheduled events in session for later use??
        return resp

    # GET: just render the page
    return render(request, 'view_calendar.html', {'events': events})