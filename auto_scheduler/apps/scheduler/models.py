"""
Models for Calendar and Event management
Along with instance methods

Authors: Reeny Huang
Created: November 10, 2025
Last Modified: November 19, 2025
"""
from datetime import datetime, timedelta
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError

User = get_user_model()

# -----------------------------------
# QuerySets & Managers
# -----------------------------------
class EventQuerySet(models.QuerySet):
    def for_user(self, user):
        """All events belonging to calendars owned by this user."""
        return self.filter(calendar__owner=user)

    def for_calendar(self, calendar):
        """All events for a specific calendar."""
        return self.filter(calendar=calendar)

    def of_eventtype(self, event_type):
        """
        Filter by EventType instance OR name string.
        Usage:
            Event.objects.of_type(some_type)
            Event.objects.of_type("School")
        """
        if isinstance(event_type, str):
            return self.filter(event_type__name=event_type)
        return self.filter(event_type=event_type)

    def upcoming(self):
        """Events starting now or in the future (ordered by start_time)."""
        return self.filter(start_time__gte=timezone.now()).order_by("start_time")

    def between(self, start, end):
        """
        Events that overlap a time range (start, end)
        Events that are 'touching' do not count as overlap (works with datetimes)
        """
        return self.filter(start_time__lt=end, end_time__gt=start)


class EventManager(models.Manager):
    def get_queryset(self):
        return (
            EventQuerySet(self.model, using=self._db).select_related("calendar", "event_type", "calendar__owner")
        )

    def for_user(self, user):
        return self.get_queryset().for_user(user)

    def for_calendar(self, calendar):
        return self.get_queryset().for_calendar(calendar)

    def of_eventtype(self, event_type):
        return self.get_queryset().of_eventtype(event_type)

    def upcoming(self):
        return self.get_queryset().upcoming()

    def between(self, start, end):
        return self.get_queryset().between(start, end)

# -----------------------------------
# Models
# -----------------------------------
class Calendar(models.Model):
    '''
    Calendar only contains calendars
    User can have more than 1 calendar
    '''
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calendars')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "calendar"
        ordering = ['created_at']
        constraints = [
            models.UniqueConstraint(fields=['owner', 'name'], name='unique_calendar_per_user')
        ]
    
    def __str__(self):
        owner_name = getattr(self.owner, 'username', str(self.owner_id))
        return f"{self.name} (Owner: {owner_name})"
    
    # -----------------------------------
    # Helper methods
    # -----------------------------------

    def all_events(self):
        '''
        Return all events associated with this calendar
        '''
        return self.events.all()
    
    def create_event(self, summary, start_time, end_time, event_type, description=None, location=None, alarm=False):
        '''
        Create an event associated with this calendar
        '''
        if end_time <= start_time:
            raise ValidationError("End time must be after start time.")
        
        event = Event.objects.create(
            calendar=self,
            summary=summary,
            start_time=start_time,
            end_time=end_time,
            duration=end_time - start_time,
            event_type=event_type,
            description=description,
            location=location,
            alarm=alarm,
        )
        return event
    
    def clear_events(self):
        '''
        Delete all events associated with this calendar
        '''
        self.events.all().delete()
    
    def delete_events_between(self, start, end):
        '''
        Delete events associated with this calendar between start and end datetime
        '''
        return (Event.objects.for_calendar(self).between(start, end).delete())
    
    def events_between(self, start, end):
        '''
        Return all events between start and end datetime
        '''
        return Event.objects.for_calendar(self).between(start, end)
    
    def events_on_date(self, date):
        '''
        Return all events on a specific date
        '''
        start_of_day = timezone.make_aware(datetime.combine(date, datetime.min.time()))
        if timezone.is_naive(start_of_day):
            start_of_day = timezone.make_aware(
                start_of_day, timezone.get_current_timezone()
            )
        end_of_day = start_of_day + timedelta(days=1)
        return Event.objects.for_calendar(self).between(start_of_day, end_of_day)
    
    def has_conflict(self, start_time, end_time, exclude_event=None):
        '''
        Check if there is a conflict with existing events in this calendar
        '''
        conflicts = Event.objects.for_calendar(self).between(start_time, end_time)
        if exclude_event:
            conflicts = conflicts.exclude(id=exclude_event.id)
        return conflicts.exists()
    
    def merge_from(self, other_calendar):
        '''
        Simply merge all events from another calendar into this calendar
        '''
        Event.objects.for_calendar(other_calendar).update(calendar=self)
        return self
    
class EventType(models.Model):
    '''
    Event type labels, shared across calendars
    '''
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "event_type"
    
    def __str__(self):
        return self.name
    
class Event(models.Model):
    '''
    Event model to store event details and belongs to a specific calendar
    Event table contains all events from all calendars
    '''
    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE, related_name='events')
    event_type = models.ForeignKey(EventType, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    summary = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    duration = models.DurationField(blank=True, null=True)
    location = models.CharField(max_length=200, blank=True, null=True)
    alarm = models.BooleanField(default=False)

    objects = EventManager()

    class Meta:
        db_table = "event"
        ordering = ['start_time']
        indexes = [
            models.Index(fields=["calendar", "start_time"]),
            models.Index(fields=["start_time"]),
            models.Index(fields=["event_type"]),
        ]

    def __str__(self):
        return self.summary
    
    def safe(self):
        if self.end_time and self.start_time and self.end_time <= self.start_time:
            raise ValidationError("End time must be after start time.")
    
    def save(self, *args, **kwargs):
        self.safe()
        if not self.duration and self.start_time and self.end_time:
            self.duration = self.end_time - self.start_time
        super().save(*args, **kwargs)

    # -----------------------------------
    # Helper methods
    # -----------------------------------
    def is_upcoming(self):
        '''
        Check if the event is upcoming
        '''
        return self.start_time >= timezone.now()
    
    def is_ongoing(self):
        '''
        Check if the event is ongoing
        '''
        now = timezone.now()
        return self.start_time <= now < self.end_time
    
    def is_past(self):
        '''
        Check if the event is in the past
        '''
        return self.end_time < timezone.now()
    
    def overlaps(self, start, end):
        '''
        Check if the event overlaps with a given time range (start, end)
        '''
        return self.start_time < end and self.end_time > start
    
    def reschedule(self, new_start_time, new_end_time):
        '''
        Reschedule the event to new start and end times
        '''
        self.start_time = new_start_time
        self.end_time = new_end_time
        self.duration = new_end_time - new_start_time
        self.save()
        return self
    
    def move_to_calendar(self, new_calendar):
        '''
        Move the event to a different calendar
        '''
        self.calendar = new_calendar
        self.save()
        return self
    
    def change_type(self, new_event_type):
        '''
        Change the event type
        '''
        self.event_type = new_event_type
        self.save()
        return self
    
    def delete_from_calendar(self):
        '''
        Delete the event from its calendar
        '''
        self.delete()
        return None