'''
Name: apps/import_events/urls.py
Description: URL configurations for import events app.
Authors: Kiara Grimsley
Created: October 26, 2025
Last Modified: October 26, 2025
'''

from django.urls import path
from . import views

urlpatterns = [
    path('import_events/', views.import_events, name='import_events'),
]
