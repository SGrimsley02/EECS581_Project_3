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
from django.http import StreamingHttpResponse
from .forms import ICSUploadForm
from .utils.icsImportExport import import_ics, export_ics


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
    return render(request, 'scheduler/upload_ics.html', {'form': form}) # Render

def add_events(request): # TODO: Ella + Hart
    '''
    View to add new events to a calendar after ICS upload.
    Exact form TBD.
    '''

    # TODO: Allow user to add events with details
        # Probably a FormSet of some sort that you can add in forms.py

    # Bypass for testing
    request.method = 'POST'

    if request.method == 'POST': # On submission
        # TODO: Safely add the events to the database
            # Put logic to add events to DB as a utils/ model

        return redirect("scheduler:view_calendar") # Redirect to view + export page

    return render(request, 'scheduler/add_events.html') # Render form to add events

def view_calendar(request): # TODO: Kiara
    '''
    View to display calendar events and allow ICS export.
    '''

    events = request.session.get('parsed_events', []) # Get events from session
    if not events: # If no events in session, error handling
        # Test events
        events = import_ics('data/sample2.ics')
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

    return render(request, 'scheduler/view_calendar.html', {'events': events}) # Render calendar view

