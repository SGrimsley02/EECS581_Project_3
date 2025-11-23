from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.scheduler.models import Calendar, Event, EventType

User = get_user_model()

class CalendarEventMinimalTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="password123",
        )
        self.calendar = Calendar.objects.create(
            owner=self.user,
            name="School",
        )
        self.event_type = EventType.objects.create(name="Study")

        self.now = timezone.now()
        self.start = self.now + timedelta(hours=1)
        self.end = self.start + timedelta(hours=2)

        self.event = self.calendar.create_event(
            summary="Study Session",
            start_time=self.start,
            end_time=self.end,
            event_type=self.event_type,
            description="EECS 581",
            location="Library",
            alarm=True,
        )

    # -----------------------------------
    # Calendar methods
    # -----------------------------------
    def test_create_event_and_all_events(self):
        events = self.calendar.all_events()
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.first(), self.event)

    def test_events_between(self):
        qs = self.calendar.events_between(self.start, self.end)
        self.assertIn(self.event, qs)

        qs2 = self.calendar.events_between(
            self.end + timedelta(hours=1),
            self.end + timedelta(hours=2),
        )
        self.assertNotIn(self.event, qs2)

    def test_has_conflict(self):
        has_conflict = self.calendar.has_conflict(
            self.start + timedelta(minutes=10),
            self.end - timedelta(minutes=10),
        )
        self.assertTrue(has_conflict)

        has_conflict2 = self.calendar.has_conflict(
            self.end + timedelta(hours=1),
            self.end + timedelta(hours=2),
        )
        self.assertFalse(has_conflict2)

    # -----------------------------------
    # Event methods
    # -----------------------------------
    def test_event_is_upcoming_and_past(self):
        self.assertTrue(self.event.is_upcoming())
        self.assertFalse(self.event.is_past())

        past_start = self.now - timedelta(hours=2)
        past_end = self.now - timedelta(hours=1)
        self.event.reschedule(past_start, past_end)

        self.assertFalse(self.event.is_upcoming())
        self.assertTrue(self.event.is_past())

    def test_event_overlaps(self):
        self.assertTrue(
            self.event.overlaps(
                self.start + timedelta(minutes=10),
                self.end - timedelta(minutes=10),
            )
        )

        self.assertFalse(
            self.event.overlaps(
                self.end + timedelta(hours=1),
                self.end + timedelta(hours=2),
            )
        )

class EventManagerMinimalTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="u1", password="pass")
        self.user2 = User.objects.create_user(username="u2", password="pass")

        self.cal1 = Calendar.objects.create(owner=self.user1, name="Cal1")
        self.cal2 = Calendar.objects.create(owner=self.user2, name="Cal2")

        self.event_type = EventType.objects.create(name="Study")

        now = timezone.now()
        self.e1 = self.cal1.create_event(
            summary="Study 1",
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            event_type=self.event_type,
        )
        self.e2 = self.cal2.create_event(
            summary="Study 2",
            start_time=now + timedelta(hours=3),
            end_time=now + timedelta(hours=4),
            event_type=self.event_type,
        )

    def test_for_user(self):
        qs1 = Event.objects.for_user(self.user1)
        qs2 = Event.objects.for_user(self.user2)

        self.assertIn(self.e1, qs1)
        self.assertNotIn(self.e2, qs1)

        self.assertIn(self.e2, qs2)
        self.assertNotIn(self.e1, qs2)

    def test_between_manager(self):
        now = timezone.now()
        qs = Event.objects.between(
            now + timedelta(minutes=30),
            now + timedelta(hours=2, minutes=30),
        )
        self.assertIn(self.e1, qs)
        self.assertNotIn(self.e2, qs)