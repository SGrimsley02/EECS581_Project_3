/*
Name: static/scheduler/js/calendar.js
Description: JavaScript code to initialize and configure the FullCalendar instance
                for displaying scheduled events in the calendar view.
Authors: Kiara Grimsley
Created: November 18, 2025
Last Modified: November 18, 2025
*/

document.addEventListener("DOMContentLoaded", function() {
    const calendarEl = document.getElementById("calendar");
    const initial_date = calendarEl.dataset.initialDate;

    const calendar = new FullCalendar.Calendar(calendarEl, {
        // Documentation: https://fullcalendar.io/docs
        // Calendar Options
        initialView: "dayGridMonth",
        initialDate: initial_date,
        headerToolbar: {
            left: "prev,next today",
            center: "title",
            right: "dayGridMonth,timeGridWeek,timeGridDay"
        },
        events: "/events/", // JSON event feed from Django
        editable: true,
        selectable: true,
        // Event Handlers
        eventClick: function(info) { // Handler for clicking on an event
            alert("Event: " + info.event.title);
        },
        eventDrop: function(info) { // Handler for dragging & dropping an event
            console.log("Moved event:", info.event);
        },
        eventResize: function(info) { // Handler for resizing an event
            console.log("Resized event:", info.event);
        }
    });

    calendar.render();
});