'''
Name: apps/export_events/urls.py
Description: URL configurations for export events app.
Authors: Kiara Grimsley
Created: October 26, 2025
Last Modified: October 26, 2025
'''

from django.urls import path
from . import views

urlpatterns = [
    path('export_events/', views.export_events, name='export_events'),
]
