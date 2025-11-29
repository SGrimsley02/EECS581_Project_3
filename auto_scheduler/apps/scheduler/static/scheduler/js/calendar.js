/*
Name: static/scheduler/js/calendar.js
Description: JavaScript code to initialize and configure the FullCalendar instance
                for displaying scheduled events in the calendar view.
Authors: Kiara Grimsley
Created: November 18, 2025
Last Modified: November 26, 2025
*/

document.addEventListener("DOMContentLoaded", function() {
    const calendarEl = document.getElementById("calendar");
    const initial_date = calendarEl.dataset.initialDate;

    let eventId = null; // Event id for deletion and editing
    let lastViewType = "dayGridMonth"; // Track last view type to reset to today's date on view change

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
        eventResizableFromStart: true,
        // Calendar Hooks
        eventClick: function(info) { // Handler for clicking on an event
            // Get event details
            const eventObj = info.event;
            const props = eventObj.extendedProps || {};
            eventId = eventObj.id;

            // Display detailed event
            document.getElementById("modal-event-title").innerText = eventObj.title;
            document.getElementById("modal-event-description").innerText = props.description || " ";
            document.getElementById("modal-event-start").value = toDatetimeLocal(eventObj.start);
            document.getElementById("modal-event-end").value = eventObj.end ? toDatetimeLocal(eventObj.end) : "";


            document.getElementById("modal-event-type").innerHTML = "";
            EVENT_TYPES.forEach(element => {
                const opt = document.createElement("option");
                opt.value = element;
                opt.textContent = element;
                if (props.event_type === element) {
                    opt.selected = true;
                }
                document.getElementById("modal-event-type").appendChild(opt);
            });

            // Show modal
            document.getElementById("modal-overlay").style.display = "flex";
            // TODO: Add customization code here so user can edit/delete event

        },
        eventDrop: function(info) { // Handler for dragging & dropping an event
            const eventObj = info.event;
            eventId = eventObj.id;

            const payload = { // Event details
                title: eventObj.title,
                description: eventObj.extendedProps.description || "",
                start: eventObj.start.toISOString(),
                end: eventObj.end ? eventObj.end.toISOString() : null,
                event_type: eventObj.extendedProps.event_type || "",
            }
            // Edit request to server
            const url = window.EDIT_EVENT_URL.replace("EVENT_ID_PLACEHOLDER", eventId);
            fetch(url, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken"),
                },
                body: JSON.stringify(payload),
            })
            .then(res => res.json())
            .then(() => {
                calendar.refetchEvents();
                document.getElementById("modal-overlay").style.display = "none";
            })
            .catch(error => {
                alert("Error rescheduling event.");
                console.error("Error rescheduling event:", error);
                info.revert(); // Revert the change
            });
        },
        eventResize: function(info) { // Handler for resizing an event
            const eventObj = info.event;
            eventId = eventObj.id;
            const payload = { // Event details
                title: eventObj.title,
                description: eventObj.extendedProps.description || "",
                start: eventObj.start.toISOString(),
                end: eventObj.end ? eventObj.end.toISOString() : null,
                event_type: eventObj.extendedProps.event_type || "",
            }
            // Edit request to server
            const url = window.EDIT_EVENT_URL.replace("EVENT_ID_PLACEHOLDER", eventId);
            fetch(url, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken"),
                },
                body: JSON.stringify(payload),
            })
            .then(res => res.json())
            .then(() => {
                calendar.refetchEvents();
                document.getElementById("modal-overlay").style.display = "none";
            })
            .catch(error => {
                alert("Error resizing event.");
                console.error("Error resizing event:", error);
                info.revert(); // Revert the change
            });
        },
        datesSet: function(info) { // Handler for today's date on view change
            if (info.view.type !== lastViewType) {
                calendar.gotoDate(new Date());
            }
            lastViewType = info.view.type;
        },
    });

    calendar.render();

    // Modal close handler
    document.getElementById("modal-close").addEventListener("click", function() {
        document.getElementById("modal-overlay").style.display = "none";
    });

    // Delete event handler
    document.getElementById("delete-event-button").addEventListener("click", function() {
        if (!eventId) return;

        const url = window.DELETE_EVENT_URL.replace("EVENT_ID_PLACEHOLDER", eventId);
        console.log("Delete URL: " + url);

        // Delete request to server
        fetch(url, {
            method: "POST",
            headers: {
                "X-CSRFToken": getCookie("csrftoken"),
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            body: JSON.stringify({})
        })
        .then(response => {
            if (response.ok) {
                // Remove event from calendar
                const event = calendar.getEventById(eventId);
                if (event) {
                    event.remove();
                }
                // Close modal
                document.getElementById("modal-overlay").style.display = "none";
            } else {
                alert("Failed to delete event.");
            }
        })
        .then(data => {
            console.log("Delete event response:", data);

            // refresh calendar
            calendar.refetchEvents();
        })
        .catch(error => {
            console.error("Error deleting event:", error);
            alert("Error deleting event.");
        });
    });

    // Save event edits handler
    document.getElementById("save-event-button").addEventListener("click", function() {
        if (!eventId) return;

        // Event data
        const payload = {
            title: document.getElementById("modal-event-title").innerText.trim(),
            description: document.getElementById("modal-event-description").innerText.trim(),
            start: document.getElementById("modal-event-start").value,
            end: document.getElementById("modal-event-end").value,
            event_type: document.getElementById("modal-event-type").value,
        };

        // Send update request to server
        const url = window.EDIT_EVENT_URL.replace("EVENT_ID_PLACEHOLDER", eventId);
        fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
            },
            body: JSON.stringify(payload),
        })
        .then(res => res.json())
        .then(() => {
            calendar.refetchEvents();
            document.getElementById("modal-overlay").style.display = "none";
        });
    });
});


// Helper function to get CSRF token from cookies
function getCookie(name) {
    let cookieValue = null;
    // Check if cookies are present
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.startsWith(name + "=")) { // Found desired cookie
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Helper function to convert Date to datetime-local string
function toDatetimeLocal(date) {
    const dt = new Date(date.getTime() - (date.getTimezoneOffset() * 60000));
    return dt.toISOString().slice(0,16);
}