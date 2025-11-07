'''
Name: apps/scheduler/urls.py
Description: URL configurations for the scheduler.
Authors: Kiara Grimsley
Created: October 26, 2025
Last Modified: November 7, 2025
'''

from django.urls import path
from django.shortcuts import redirect
from . import views

app_name = "scheduler"

urlpatterns = [
    path('', lambda request: redirect('scheduler:upload_ics')),
    path('upload_ics/', views.upload_ics, name='upload_ics'),
    path('add_events/', views.add_events, name='add_events'),
    path('view_calendar/', views.view_calendar, name='view_calendar'),
]
