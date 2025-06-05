function updateAssignmentBadge() {
    fetch('/interpreter/assignments/notifications/count/')
        .then(response => response.json())
        .then(data => {
            const badge = document.getElementById('assignment-badge');
            const iconWrapper = document.querySelector('.notification-icon-wrapper');
            
            if (data.count > 0) {
                badge.textContent = data.count;
                badge.style.display = 'flex';
                iconWrapper.classList.add('shake');
            } else {
                badge.style.display = 'none';
                iconWrapper.classList.remove('shake');
            }
        });
}

function initializeNotifications() {
    updateAssignmentBadge();
    setInterval(updateAssignmentBadge, 30000);

    document.querySelector('.nav-item').addEventListener('click', function() {
        const iconWrapper = this.querySelector('.notification-icon-wrapper');
        iconWrapper.classList.remove('shake');
        fetch('/interpreter/assignments/notifications/mark-read/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            }
        });
    });
}

document.addEventListener('DOMContentLoaded', initializeNotifications);