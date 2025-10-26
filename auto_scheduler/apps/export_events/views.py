'''
Name: apps/export_events/views.py
Description: Views for handling export events functionality.
Authors: Kiara Grimsley
Created: October 26, 2025
Last Modified: October 26, 2025
'''

from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader

def export_events(request):
    template = loader.get_template('export.html')
    return HttpResponse(template.render())