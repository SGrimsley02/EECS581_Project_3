'''
Name: apps/scheduler/forms.py
Description: Forms for file uploading in the scheduler app and study preferences questionnaire.
Authors: Kiara Grimsley, Audrey Pan
Created: November 7, 2025
Last Modified: November 9, 2025
'''

from django import forms

class ICSUploadForm(forms.Form):
    '''Upload field for .ics files. Accepts only files with .ics extension'''

    ics_file = forms.FileField(
        label="Upload ICS File",
        help_text="Select a .ics file to upload.",
        widget=forms.ClearableFileInput(attrs={'accept': '.ics'})
    )

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

    # Weekend rules for whether the scheduler may assign study sessions
    WEEKENDS_CHOICES = [
        ("yes", "Yes (Saturday and Sunday)"),
        ("no", "No"),
        ("sunday_only", "Only Sundays"),
    ]
    weekends = forms.ChoiceField(label="Do you want study sessions on weekends?", choices=WEEKENDS_CHOICES)

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