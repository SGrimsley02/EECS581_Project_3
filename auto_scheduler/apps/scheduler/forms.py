'''
Name: apps/scheduler/forms.py
Description: Forms for file uploading in the scheduler app and study preferences questionnaire.
Authors: Kiara Grimsley, Ella Nguyen, Audrey Pan
Created: November 7, 2025
Last Modified: November 16, 2025
'''

from django import forms
from .utils.constants import EventType, PRIORITY_CHOICES

class ICSUploadForm(forms.Form):
    '''Upload field for .ics files. Accepts only files with .ics extension'''

    ics_file = forms.FileField(
        label="Upload ICS File",
        help_text="Select a .ics file to upload.",
        widget=forms.ClearableFileInput(attrs={'accept': '.ics'}),
        error_messages={"required": "Please select a .ics file to upload."}
    )

class EventForm(forms.Form):
    '''
    Collects details about single event user wants to schedule.
    Used in FormSet so multiple events can be added on 'Add Events' page
    '''

    # Short text title for the event
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
                "placeholder": "Add an optional note or details about this event...",
                "rows": 2,
                "cols": 40,
            }
        ),
        help_text="(Optional) Brief note to describe the event.",
    )

    # Event duration in minutes
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
        choices=EventType.choices,
        label="Event Type",
        help_text="Select the general category of this event."
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

    # Allow splitting long events into smaller chunks
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
        '''
        Ensures date/time ranges are logical + Split block logic
        '''
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

class StudyPreferencesForm(forms.Form):
    '''Initial study preferences questionnaire'''

    # Ranking 1-6 for each time window (1 = best). Stored as strings and validated for uniqueness.
    RANK_CHOICES = [(i, str(i)) for i in range(1, 7)]
    early_morning_rank = forms.ChoiceField(label="Early Morning (5-9 AM)", choices=RANK_CHOICES)
    late_morning_rank  = forms.ChoiceField(label="Late Morning (9 AM-12 PM)", choices=RANK_CHOICES)
    afternoon_rank     = forms.ChoiceField(label="Afternoon (12-4 PM)", choices=RANK_CHOICES)
    evening_rank       = forms.ChoiceField(label="Evening (4-8 PM)", choices=RANK_CHOICES)
    night_rank         = forms.ChoiceField(label="Night (8 PM-12 AM)", choices=RANK_CHOICES)
    late_night_rank    = forms.ChoiceField(label="Late Night (12-5 AM)", choices=RANK_CHOICES)

    # Preferred length of an individual study session
    IDEAL_LEN_CHOICES = [
        ("30m", "30 minutes"),
        ("1h", "1 hour"),
        ("1h30", "1.5 hours"),
        ("2h_plus", "2+ hours"),
    ]
    ideal_length = forms.ChoiceField(label="How long is your ideal study session?", choices=IDEAL_LEN_CHOICES)

    # Single long session vs multiple short sessions
    SESSION_STYLE_CHOICES = [
        ("single", "One long study session"),
        ("multiple", "Multiple shorter study sessions"),
    ]
    session_style = forms.ChoiceField(label="Do you prefer", choices=SESSION_STYLE_CHOICES)

    # Maximum number of total study hours per day the system should schedule
    max_hours_per_day = forms.IntegerField(label="Max hours per day to study", min_value=0, max_value=24)

    # Wake and sleep times (stored as "HH:MM" string later in session)
    wake_time = forms.TimeField(label="What time do you usually wake up?", widget=forms.TimeInput(attrs={'type': 'time'}))
    bed_time  = forms.TimeField(label="What time do you usually go to bed?", widget=forms.TimeInput(attrs={'type': 'time'}))

    # Days to fully block out from scheduling
    DAYS = [
        ("mon", "Monday"), ("tue", "Tuesday"), ("wed", "Wednesday"),
        ("thu", "Thursday"), ("fri", "Friday"), ("sat", "Saturday"), ("sun", "Sunday"),
    ]
    blackout_days = forms.MultipleChoiceField(
        label="Days you never want study sessions (select any)",
        choices=DAYS,
        required=False,
        widget=forms.CheckboxSelectMultiple
    )

    # How far in advance the student likes to begin exam prep
    LOOKAHEAD_CHOICES = [
        ("1_3", "1-3 days"),
        ("4_6", "4-6 days"),
        ("1w",  "1 week"),
        ("2w+", "2 weeks +"),
    ]
    lookahead = forms.ChoiceField(label="How far in advance to study for exams?", choices=LOOKAHEAD_CHOICES)

    def clean(self):
        '''Ensure all ranks 1-6 are unique'''
        cleaned = super().clean()

        # Extract all rank selections
        ranks = [
            cleaned.get("early_morning_rank"),
            cleaned.get("late_morning_rank"),
            cleaned.get("afternoon_rank"),
            cleaned.get("evening_rank"),
            cleaned.get("night_rank"),
            cleaned.get("late_night_rank"),
        ]

        # Only validate if all ranks exist (avoids None comparison issues)
        if None not in ranks and len(set(ranks)) != 6:
            raise forms.ValidationError("Please assign a unique rank (1-6) to each time window.")
        return cleaned