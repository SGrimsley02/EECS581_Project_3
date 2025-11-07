'''
Name: apps/scheduler/forms.py
Description: Forms for file uploading in the scheduler app.
Authors: Kiara Grimsley
Created: November 7, 2025
Last Modified: November 7, 2025
'''

from django import forms

class ICSUploadForm(forms.Form):
    '''Upload field for .ics files. Accepts only files with .ics extension'''

    ics_file = forms.FileField(
        label="Upload ICS File",
        help_text="Select a .ics file to upload.",
        widget=forms.ClearableFileInput(attrs={'accept': '.ics'})
    )
