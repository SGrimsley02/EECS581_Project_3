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
from apps.scheduler.utils.event_types import EventType
import pytz
import re

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
                "recurrence": next((e.value for e in ics_event.extra if e.name == "RRULE"), None),
                "event_type": ics_event.categories,
                # If any more fields needed, add them here
            }
            categorize_event(event) # Add category to event
            events.append(event)
    return events

def categorize_event(event):
    """
    Categorizes an event based on its name or description. Then, appends the category to the event dictionary.
    Parameters:
        event: Dict of event to categorize.
    Returns:
        None
    """
    name = event["name"].lower()
    start = event["start"]
    end = event["end"]
    description = event["description"].lower()
    recurrence = event["recurrence"]
    

    if re.search(r"\b(study|review|homework|assignment|exam|project|prep|test|quiz)\b", name + " " + description):
        event["event_type"] = EventType.STUDY.value
        
    elif re.search(r"\b(class|lecture|seminar|course|lab|discussion)\b", name + " " + description):
        event["event_type"] = EventType.CLASS.value
    
    # Checks for common course code patterns (e.g., EECS 101, MATH202)
    elif re.search(r"[A-Z]{2,4}\s?\d{3}", name + " " + description):
        event["event_type"] = EventType.CLASS.value
    
    elif re.search(r"\b(dinner|fun|party|game|movie|concert|outing|lunch|chill|hang|hangout|friends|birthday|bday|relax|date|coffee|break)\b", name + " " + description):
        event["event_type"] = EventType.LEISURE.value
    
    elif re.search(r"\b(work|meeting|call|presentation|deadline|office|shift|job|internship)\b", name + " " + description):
        event["event_type"] = EventType.WORK.value
    
    elif re.search(r"\b(workout|gym|doctor|workout)\b", name + " " + description):
        event["event_type"] = EventType.OTHER.value
    
    elif start:
        start_hour = start.time().hour
        duration_hours = ((end - start).seconds / 3600) if end else None

        # Likely class: between 8am-5pm, recurring, 30min-2hr
        if 8 <= start_hour <= 17 and recurrence and duration_hours and 0.5 <= duration_hours <= 2:
            event["event_type"] = EventType.CLASS.value
        
        # Likely work: between 8am-10pm, recurring, 2hr+
        elif 8 <= start_hour <= 22 and recurrence and duration_hours and duration_hours >= 2:
            event["event_type"] = EventType.WORK.value   
    return

# Example usage:
# sample2_events = import_ics("data/sample2.ics")
# print("Imported Events:", sample2_events)

# export_ics(sample2_events)
# print("Exported Events to exported_sample2.ics")
