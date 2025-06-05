// Initialisation du calendrier
document.addEventListener('DOMContentLoaded', function() {
    const calendarEl = document.getElementById('calendar');
    let calendar;

    // Configuration des status et leurs couleurs
    const statusColors = {
        'PENDING': '#FFA500',    // Orange
        'ASSIGNED': '#4299e1',   // Bleu clair
        'CONFIRMED': '#48bb78',  // Vert
        'IN_PROGRESS': '#805ad5', // Violet
        'COMPLETED': '#718096',  // Gris
        'CANCELLED': '#f56565',  // Rouge
        'NO_SHOW': '#ed8936',    // Orange foncé
    };

    // Configuration du calendrier
    calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        height: '100%',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay'
        },
        themeSystem: 'standard',
        dayMaxEvents: true,
        eventTimeFormat: {
            hour: 'numeric',
            minute: '2-digit',
            meridiem: 'short'
        },
        firstDay: 1,
        slotMinTime: '07:00:00',
        slotMaxTime: '21:00:00',
        slotDuration: '00:30:00',
        expandRows: true,
        handleWindowResize: true,
        stickyHeaderDates: true,
        
        events: function(info, successCallback, failureCallback) {
            fetch(`/interpreter/schedule/assignments/?start=${info.startStr}&end=${info.endStr}`)
                .then(response => response.json())
                .then(data => {
                    successCallback(data);
                })
                .catch(error => {
                    console.error('Error fetching events:', error);
                    failureCallback(error);
                });
        },

        eventDidMount: function(info) {
            initializeTooltip(info.el, info.event);
        },

        eventClick: function(info) {
            showEventDetails(info.event);
        },

        loading: function(isLoading) {
            if (isLoading) {
                calendarEl.classList.add('loading');
            } else {
                calendarEl.classList.remove('loading');
            }
        }
    });

    // Rendu du calendrier
    calendar.render();

    // Gestion des boutons de navigation rapide
    document.getElementById('todayBtn').addEventListener('click', () => {
        calendar.today();
    });

    document.getElementById('weekBtn').addEventListener('click', () => {
        calendar.changeView('timeGridWeek');
    });

    document.getElementById('monthBtn').addEventListener('click', () => {
        calendar.changeView('dayGridMonth');
    });

    document.getElementById('refreshBtn').addEventListener('click', () => {
        calendar.refetchEvents();
    });

    // Fonctions de tooltip
    function initializeTooltip(element, event) {
        if (currentTooltip) {
            currentTooltip.destroy();
        }

        const tooltip = createTooltipContent(event);
        
        currentTooltip = Popper.createPopper(element, tooltip, {
            placement: 'top',
            modifiers: [
                {
                    name: 'offset',
                    options: { offset: [0, 8] }
                },
                {
                    name: 'preventOverflow',
                    options: { padding: 8 }
                }
            ]
        });

        element.addEventListener('mouseenter', () => {
            tooltip.style.display = 'block';
        });

        element.addEventListener('mouseleave', () => {
            tooltip.style.display = 'none';
        });
    }

    function createTooltipContent(event) {
        const props = event.extendedProps;
        const tooltip = document.createElement('div');
        tooltip.className = 'event-tooltip';
        tooltip.style.display = 'none';
        
        tooltip.innerHTML = `
            <div class="tooltip-content">
                <div class="tooltip-header">
                    <span class="status-badge status-${props.status.toLowerCase()}">${props.status}</span>
                </div>
                <div class="tooltip-body">
                    <p><i class="fas fa-language"></i> ${props.languages}</p>
                    <p><i class="fas fa-map-marker-alt"></i> ${props.location}</p>
                    <p><i class="fas fa-clock"></i> ${props.hours.toFixed(1)}h</p>
                    <p><i class="fas fa-dollar-sign"></i> $${props.rate}/hour</p>
                </div>
            </div>
        `;

        document.body.appendChild(tooltip);
        return tooltip;
    }

    // Fonction pour afficher les détails d'un événement
    function showEventDetails(event) {
        const modal = document.getElementById('eventModal');
        const modalContent = modal.querySelector('.modal-content');
        const props = event.extendedProps;

        modalContent.innerHTML = `
            <div class="modal-header">
                <h2>${event.title}</h2>
                <button class="close-modal">&times;</button>
            </div>
            <div class="modal-body">
                <div class="event-details">
                    <div class="detail-row">
                        <span class="label">Status:</span>
                        <span class="value status-badge status-${props.status.toLowerCase()}">${props.status}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Date & Time:</span>
                        <span class="value">${formatDateTime(event.start)} - ${formatDateTime(event.end)}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Languages:</span>
                        <span class="value">${props.languages}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Location:</span>
                        <span class="value">${props.location}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Rate:</span>
                        <span class="value">$${props.rate}/hour</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Duration:</span>
                        <span class="value">${props.hours.toFixed(1)} hours</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Total Payment:</span>
                        <span class="value">$${props.total_payment.toFixed(2)}</span>
                    </div>
                    ${props.special_requirements ? `
                    <div class="detail-row">
                        <span class="label">Special Requirements:</span>
                        <span class="value">${props.special_requirements}</span>
                    </div>
                    ` : ''}
                </div>
            </div>
        `;

        modal.style.display = 'block';

        // Gestion de la fermeture de la modal
        const closeBtn = modalContent.querySelector('.close-modal');
        closeBtn.addEventListener('click', () => {
            modal.style.display = 'none';
        });

        window.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });
    }

    // Fonction utilitaire pour formater la date et l'heure
    function formatDateTime(date) {
        return new Date(date).toLocaleString('en-US', {
            weekday: 'short',
            month: 'short',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });
    }
});