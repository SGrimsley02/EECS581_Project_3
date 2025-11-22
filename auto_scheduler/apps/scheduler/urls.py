'''
Name: apps/scheduler/urls.py
Description: URL configurations for the scheduler.
Authors: Kiara Grimsley, Audrey Pan
Created: October 26, 2025
Last Modified: November 22, 2025
'''

from django.urls import path, include
from django.shortcuts import redirect
from .views import preferences, upload_ics, add_events, view_calendar, auth_view, home, event_feed, dismiss_preferences_recap, event_stats

app_name = "scheduler"

urlpatterns = [
    path("accounts/", include("django.contrib.auth.urls")),
    path('signup/', auth_view, name='signup'),
    path('', home, name='home'),
    path('preferences/', preferences, name='preferences'),
    path('upload_ics/', upload_ics, name='upload_ics'),
    path('add_events/', add_events, name='add_events'),
    path('view_calendar/', view_calendar, name='view_calendar'),
    path('events/', event_feed, name='event_feed'),
    path("preferences/dismiss-recap/", dismiss_preferences_recap, name="dismiss_preferences_recap"),
    path('stats/', event_stats, name='event_stats'),

]
