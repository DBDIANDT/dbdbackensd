// Fonction pour obtenir le token CSRF
function getCsrfToken() {
    const csrfCookie = document.cookie
        .split(';')
        .find(cookie => cookie.trim().startsWith('csrftoken='));
    return csrfCookie ? csrfCookie.split('=')[1] : null;
}

// Fonction pour mettre à jour le statut
function updateStatus(assignmentId, newStatus) {
    const csrfToken = getCsrfToken();
    const statusIcons = {
        'PENDING': '⏳',
        'CONFIRMED': '✓',
        'IN_PROGRESS': '🔄',
        'COMPLETED': '✅',
        'CANCELLED': '❌',
        'NO_SHOW': '⚠️'
    };

    // Afficher une confirmation pour certains statuts
    if (['CANCELLED', 'COMPLETED'].includes(newStatus)) {
        if (!confirm(`Are you sure you want to mark this assignment as ${newStatus}?`)) {
            return;
        }
    }

    // Appel API pour mettre à jour le statut
    fetch(`/admin/app/assignment/${assignmentId}/update-status/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ 
            status: newStatus,
            assignment_id: assignmentId
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            // Mettre à jour l'interface utilisateur
            const statusCell = document.querySelector(`#status-${assignmentId}`);
            if (statusCell) {
                statusCell.innerHTML = `${statusIcons[newStatus]} ${newStatus}`;
                // Ajouter une classe pour l'animation de mise à jour
                statusCell.classList.add('status-updated');
            }
            // Afficher un message de succès
            showNotification('Status updated successfully', 'success');
        } else {
            showNotification(data.message || 'Update failed', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Error updating status', 'error');
    });
}

// Fonction pour afficher les notifications
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    // Animation d'entrée
    setTimeout(() => {
        notification.classList.add('show');
    }, 100);
    
    // Supprimer après 3 secondes
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 3000);
}

// Gestionnaire d'événements pour les actions rapides
document.addEventListener('DOMContentLoaded', function() {
    const actionButtons = document.querySelectorAll('.status-action-btn');
    
    actionButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            e.preventDefault();
            const assignmentId = button.dataset.assignmentId;
            const newStatus = button.dataset.status;
            updateStatus(assignmentId, newStatus);
        });
    });
});