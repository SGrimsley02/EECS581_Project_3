'''
Name: apps/scheduler/urls.py
Description: URL configurations for the scheduler.
Authors: Kiara Grimsley
Created: October 26, 2025
Last Modified: November 7, 2025
'''

from django.urls import path
from . import views

urlpatterns = [
    path('scheduler/', views.scheduler, name='scheduler'),
]
