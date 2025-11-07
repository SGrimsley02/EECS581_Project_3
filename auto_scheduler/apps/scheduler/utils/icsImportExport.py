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
    Parameters:
        events (List[Dict]): List of events (dictionaries) to export.
        file_path (str): Path to the ICS file to create.
    Returns:
        None
        Creates an ICS file at specified path with new events.
    """
    calendar = Calendar() # New calendar instance
    # Add all events to the calendar
    for event in events:
        ics_event = Event()
        ics_event.name = event.get("name", "No Title") # Event title, default No Title
        ics_event.begin = str(event.get("start", datetime.now()).astimezone(pytz.UTC)) # Event start time, default now (error?)
        ics_event.end = str(event.get("end", datetime.now()).astimezone(pytz.UTC)) # Event end time, default now (error?)
        ics_event.description = event.get("description", "") # Event description, default none
        ics_event.location = event.get("location", "") # Event location, default none
        # If any more fields needed, add them here

        # Add event to calendar
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
