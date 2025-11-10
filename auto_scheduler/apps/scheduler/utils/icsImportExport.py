'''
Name: icsImportExport.py
Description: Module for importing and exporting calendar events in ICS format.
Authors: Kiara Grimsley
Created: October 26, 2025
Last Modified: November 7, 2025
Functions: export_ics(events, file_path)
            import_ics(file_path)
'''

from datetime import datetime
from ics import Calendar, Event
import pytz

def export_ics(events): # TODO: modify to export from database
    """
    Exports a list of events to an ICS file.
    Accepts datetimes or ISO strings for start/end.

    Parameters:
        events (List[Dict]): List of events (dictionaries) to export.
        file_path (str): Path to the ICS file to create.
    Returns:
        None
        Creates an ICS file at specified path with new events.
    """

    # Helper: convert start/end from datetime object or ISO to timezone-aware UTC datetime
    def to_dt(x):
        if isinstance(x, datetime):
            return x if x.tzinfo else x.replace(tzinfo=pytz.UTC)
        try:
            # Convert ISO string to datetime
            dt = datetime.fromisoformat(str(x))
            return dt if dt.tzinfo else dt.replace(tzinfo=pytz.UTC)
        except Exception:
            return datetime.now(pytz.UTC)
    
    calendar = Calendar()
    # Add all events to the calendar
    for event in events:
        ics_event = Event()
        ics_event.name = event.get("name", "No Title") # Event title, default No Title
        start_raw = event.get("start", datetime.now()) # Raw event start time, default now (modified from prev error-causing version)
        end_raw = event.get("end", datetime.now()) # Raw event end time, default now
        ics_event.begin = to_dt(start_raw) # Event start time
        ics_event.end = to_dt(end_raw) # Event end time
        ics_event.description = event.get("description", "") # Event description, default none
        ics_event.location = event.get("location", "") # Event location, default none
        # If any more fields needed, add them here

        calendar.events.add(ics_event)

    return calendar.serialize_iter() # serialize_iter in case file gets large

def import_ics(file_path): # TODO: modify to import into database
    """
    Imports events from an ICS file and returns them as a list of dictionaries.
    Paremeters:
        file_path (str): Path to the ICS file to import.
    Returns:
        List[Dict]: List of events imported from the ICS file.
    """
    events = [] # List to hold imported events

    # Read ICS file
    with open(file_path, "r") as ics_file:
        calendar = Calendar(ics_file.read())
        for ics_event in calendar.events:
            event = {
                "name": ics_event.name,
                "start": ics_event.begin.astimezone(pytz.UTC).isoformat(),
                "end": ics_event.end.astimezone(pytz.UTC).isoformat(),
                "description": ics_event.description,
                "location": ics_event.location,
                # If any more fields needed, add them here
            }
            events.append(event)
    return events

# Example usage:
# sample2_events = import_ics("data/sample2.ics")
# print("Imported Events:", sample2_events)

# export_ics(sample2_events)
# print("Exported Events to exported_sample2.ics")
