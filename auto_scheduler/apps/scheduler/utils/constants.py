'''
Name: apps/scheduler/utils/constants.py
Description: Constants used in the scheduler app.
                Session keys
                Event types
                Priority choices
                Debug logger
Authors: Kiara Grimsley, Lauren D'Souza, Hart Nurnberg, Audrey Pan
Created: November 9, 2025
Last Modified: December 1, 2025
'''


from django.db import models

class EventType(models.TextChoices):
    CLASS = "Class"
    STUDY = "Study Session"
    LEISURE = "Leisure"
    WORK = "Work"
    OTHER = "Other"

PRIORITY_CHOICES = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
]


SESSION_EVENT_REQUESTS = "event_requests"
SESSION_IMPORTED_EVENTS = "imported_events"
SESSION_SCHEDULED_EVENTS = "scheduled_events"
SESSION_SCHEDULE_UPDATE = "schedule_update"
SESSION_FILE_PATH = "uploaded_file_path"
SESSION_PREFERENCES = "study_preferences"
SESSION_UNDO_STACK = "schedule_undo_stack"
SESSION_REDO_STACK = "schedule_redo_stack"
PREFERENCES_RECAP_DAYS = 14
SESSION_PREF_LAST_UPDATED = "preferences_last_updated"
SESSION_PREF_RECAP_DISMISSED = "preferences_recap_dismissed"
SESSION_ORIGINAL_EVENT_REQUESTS = "original_event_requests"
SESSION_ORIGINAL_IMPORTED_EVENTS = "original_imported_events"


LOGGER_NAME = "apps.scheduler"

PRIORITY_ORDER = {
    "high": 0,
    "medium": 1,
    "low": 2
}
HEAT_MONTH_OPTIONS = [
    {"value": 1,  "label": "January"},
    {"value": 2,  "label": "February"},
    {"value": 3,  "label": "March"},
    {"value": 4,  "label": "April"},
    {"value": 5,  "label": "May"},
    {"value": 6,  "label": "June"},
    {"value": 7,  "label": "July"},
    {"value": 8,  "label": "August"},
    {"value": 9,  "label": "September"},
    {"value": 10, "label": "October"},
    {"value": 11, "label": "November"},
    {"value": 12, "label": "December"},
]