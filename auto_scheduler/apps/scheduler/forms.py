'''
Name: apps/scheduler/forms.py
Description: Forms for file uploading in the scheduler app.
Authors: Kiara Grimsley, Ella Nguyen
Created: November 7, 2025
Last Modified: November 8, 2025
'''

from django import forms

class ICSUploadForm(forms.Form):
    '''Upload field for .ics files. Accepts only files with .ics extension'''

    ics_file = forms.FileField(
        label="Upload ICS File",
        help_text="Select a .ics file to upload.",
        widget=forms.ClearableFileInput(attrs={'accept': '.ics'})
    )

PRIORITY_CHOICES = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
]

EVENT_TYPES = [
    ("project", "Project"),
    ("exam", "Exam"),
    ("homework", "Homework"),
    ("meeting", "Meeting"),
    ("other", "Other"),
]

class TaskForm(forms.Form):
    '''Collects details about single task/event user wants to schedule. Used in FormSet so multiple tasks can be added on 'Add Events' page'''

    # Short text title for the task
    title = forms.CharField(
        max_length=120,
        label="Title",
        widget=forms.TextInput(
            attrs={"placeholder": "e.g., Study Linear Algebra"}
        ),
    )

    description = forms.CharField(
        required=False,
        label="Description",
        widget=forms.Textarea(
            attrs={
                "placeholder": "Add an optional note or details about this task...",
                "rows": 2,
                "cols": 40,
            }
        ),
        help_text="(Optional) Brief note to describe the task.",
    )

    # Task duration in minutes
    duration_minutes = forms.IntegerField(
        min_value=5,
        label="Duration (minutes)",
        widget=forms.NumberInput(
            attrs={"step": "5", "placeholder": "60"}  # increments of 5 min
        ),
    )

    # User-assigned priority level
    priority = forms.ChoiceField(
        choices=PRIORITY_CHOICES,
        label="Priority"
    )

    # User-assigned event type
    event_type = forms.ChoiceField(
        choices=EVENT_TYPES,
        label="Event Type",
        help_text="Select the general category of this task or event."
    )

    ''' Optional Fields(?) '''

    # Allow user to constrain scheduling dates/times
    date_start = forms.DateField(
        required=False,
        label="Earliest Date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_end = forms.DateField(
        required=False,
        label="Latest Date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    time_start = forms.TimeField(
        required=False,
        label="Earliest Time",
        widget=forms.TimeInput(attrs={"type": "time"}),
    )
    time_end = forms.TimeField(
        required=False,
        label="Latest Time",
        widget=forms.TimeInput(attrs={"type": "time"}),
    )

    # Allow splitting long tasks into smaller chunks
    split = forms.BooleanField(
        required=False,
        label="Split into smaller blocks?",
    )
    split_minutes = forms.IntegerField(
        required=False,
        min_value=5,
        label="Split block size (minutes)",
        widget=forms.NumberInput(
            attrs={"step": "5", "placeholder": "30"}
        ),
    )

    def clean(self):
        ''' Ensures date/time ranges are logical + Split block logic '''
        """
        Performs custom validation on the form's fields.
        Ensures date/time ranges are logical and that a split block
        size is provided when 'split' is checked.
        """
        cleaned = super().clean()

        # Retrieve cleaned values for convenience
        ds = cleaned.get("date_start")
        de = cleaned.get("date_end")
        ts = cleaned.get("time_start")
        te = cleaned.get("time_end")
        split = cleaned.get("split")
        split_mins = cleaned.get("split_minutes")

        # Validate date range: earliest <= latest
        if ds and de and ds > de:
            self.add_error(
                "date_end",
                "Latest Date must be on or after Earliest Date."
            )

        # Validate time range: earliest < latest
        if ts and te and ts >= te:
            self.add_error(
                "time_end",
                "Latest Time must be after Earliest Time."
            )

        # Validate split logic: if checked, split_minutes required
        if split and not split_mins:
            self.add_error(
                "split_minutes",
                "Provide a split block size when splitting is enabled."
            )

        return cleaned