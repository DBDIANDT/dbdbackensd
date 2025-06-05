// Initialisation au chargement du document
document.addEventListener('DOMContentLoaded', function() {
    initializeTabs();
    initializeCards();
    initializeModalHandlers();
    updateAssignmentCounts();
});

// Gestion des onglets
function initializeTabs() {
    const tabs = document.querySelectorAll('.tab-button');
    const contents = document.querySelectorAll('.tab-content');

    // Masquer tous les contenus sauf le premier au démarrage
    contents.forEach(content => {
        content.style.display = 'none';
    });
    document.getElementById('pending-content').style.display = 'block';

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Mise à jour des onglets
            tabs.forEach(t => t.classList.remove('active'));
            contents.forEach(content => {
                content.style.display = 'none';
                content.classList.remove('active');
            });

            // Activation de l'onglet sélectionné
            tab.classList.add('active');
            const contentId = `${tab.dataset.tab}-content`;
            const activeContent = document.getElementById(contentId);
            if (activeContent) {
                activeContent.style.display = 'block';
                activeContent.classList.add('active');
            }
        });
    });
}

// Initialisation des cartes
function initializeCards() {
    const assignmentCards = document.querySelectorAll('.assignment-card');
    assignmentCards.forEach(card => {
        card.addEventListener('click', async (e) => {
            if (!e.target.closest('.assignment-actions')) {
                const assignmentId = card.dataset.id;
                await showAssignmentDetails(assignmentId);
            }
        });
    });
}

// Initialisation des gestionnaires de modal
function initializeModalHandlers() {
    const modal = document.getElementById('assignmentModal');
    const closeButton = modal.querySelector('.modal-close');

    window.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });

    closeButton.addEventListener('click', () => {
        modal.style.display = 'none';
    });
}

// Actions sur les assignments
async function acceptAssignment(id, event) {
    event.stopPropagation();
    if (!confirm('Are you sure you want to accept this assignment?')) return;

    showLoading();
    try {
        const response = await fetch(`/interpreter/assignments/${id}/accept/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            }
        });

        const data = await response.json();
        
        if (response.ok) {
            showToast('Assignment accepted successfully');
            removeAssignmentCard(id);
            updateAssignmentCounts();
        } else {
            throw new Error(data.message || 'Failed to accept assignment');
        }
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        hideLoading();
    }
}

async function rejectAssignment(id, event) {
    event.stopPropagation();
    if (!confirm('Are you sure you want to reject this assignment?')) return;

    showLoading();
    try {
        const response = await fetch(`/interpreter/assignments/${id}/reject/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            }
        });

        const data = await response.json();

        if (response.ok) {
            showToast('Assignment rejected successfully');
            removeAssignmentCard(id);
            updateAssignmentCounts();
        } else {
            throw new Error(data.message || 'Failed to reject assignment');
        }
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        hideLoading();
    }
}

async function startAssignment(id, event) {
    event.stopPropagation();
    if (!confirm('Are you sure you want to start this assignment?')) return;

    showLoading();
    try {
        const response = await fetch(`/interpreter/assignments/${id}/start/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            }
        });

        const data = await response.json();

        if (response.ok) {
            showToast('Assignment started successfully');
            removeAssignmentCard(id);
            updateAssignmentCounts();
        } else {
            throw new Error(data.message || 'Failed to start assignment');
        }
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        hideLoading();
    }
}

async function completeAssignment(id, event) {
    event.stopPropagation();
    if (!confirm('Are you sure you want to complete this assignment?')) return;

    showLoading();
    try {
        const response = await fetch(`/interpreter/assignments/${id}/complete/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            }
        });

        const data = await response.json();

        if (response.ok) {
            showToast('Assignment completed successfully');
            removeAssignmentCard(id);
            updateAssignmentCounts();
        } else {
            throw new Error(data.message || 'Failed to complete assignment');
        }
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Gestion des détails d'assignment
async function showAssignmentDetails(id) {
    showLoading();
    try {
        const response = await fetch(`/interpreter/assignments/${id}/details/`);
        const data = await response.json();

        const modal = document.getElementById('assignmentModal');
        const modalBody = modal.querySelector('.modal-body');

        modalBody.innerHTML = generateModalContent(data);
        modal.style.display = 'block';
    } catch (error) {
        showToast('Error loading assignment details', 'error');
    } finally {
        hideLoading();
    }
}

// Gestion UI
function showLoading() {
    document.querySelector('.loading-overlay').style.display = 'flex';
}

function hideLoading() {
    document.querySelector('.loading-overlay').style.display = 'none';
}

function removeAssignmentCard(id) {
    const card = document.querySelector(`[data-id="${id}"]`);
    if (card) {
        card.style.transform = 'translateX(100%)';
        card.style.opacity = '0';
        setTimeout(() => {
            card.remove();
            checkEmptyState();
        }, 300);
    }
}

function checkEmptyState() {
    const activeContent = document.querySelector('.tab-content.active');
    if (activeContent && !activeContent.querySelector('.assignment-card')) {
        const tabName = activeContent.id.replace('-content', '');
        activeContent.innerHTML = createEmptyState(tabName);
    }
}

// Mise à jour des compteurs
async function updateAssignmentCounts() {
    try {
        const response = await fetch('/interpreter/assignments/counts/');
        const counts = await response.json();
        
        updateStatCard('pending', counts.pending);
        updateStatCard('upcoming', counts.upcoming);
        updateStatCard('in_progress', counts.in_progress);
        updateStatCard('completed', counts.completed);
        
        updateTabCounts(counts);
    } catch (error) {
        console.error('Failed to update assignment counts:', error);
    }
}

function updateStatCard(type, count) {
    const statValue = document.querySelector(`.stat-card[data-type="${type}"] .stat-value`);
    if (statValue) {
        statValue.textContent = count;
    }
}

function updateTabCounts(counts) {
    Object.entries(counts).forEach(([type, count]) => {
        const tabCount = document.querySelector(`.tab-button[data-tab="${type}"] .tab-count`);
        if (tabCount) {
            if (count > 0) {
                tabCount.textContent = count;
                tabCount.style.display = 'flex';
            } else {
                tabCount.style.display = 'none';
            }
        }
    });
}

// Génération de contenu
function createEmptyState(tabName) {
    const states = {
        pending: {
            icon: 'inbox',
            text: 'No pending assignments',
            subtext: 'New assignments will appear here'
        },
        upcoming: {
            icon: 'calendar',
            text: 'No upcoming assignments',
            subtext: 'Accepted assignments will appear here'
        },
        'in-progress': {
            icon: 'tasks',
            text: 'No assignments in progress',
            subtext: 'Active assignments will appear here'
        },
        completed: {
            icon: 'check-double',
            text: 'No completed assignments',
            subtext: 'Your completed assignments will appear here'
        }
    };

    const state = states[tabName] || states.pending;
    return `
        <div class="empty-state">
            <i class="fas fa-${state.icon} empty-state-icon"></i>
            <h3 class="empty-state-text">${state.text}</h3>
            <p class="empty-state-subtext">${state.subtext}</p>
        </div>
    `;
}

function generateModalContent(data) {
    return `
        <div class="modal-info-grid">
            <div class="info-section">
                <h3><i class="fas fa-clock"></i> Time & Date</h3>
                <p>Start: ${formatDateTime(data.start_time)}</p>
                <p>End: ${formatDateTime(data.end_time)}</p>
                <p>Duration: ${calculateDuration(data.start_time, data.end_time)}</p>
            </div>

            <div class="info-section">
                <h3><i class="fas fa-map-marker-alt"></i> Location</h3>
                <p>${data.location}</p>
                <p>${data.city}, ${data.state} ${data.zip_code}</p>
            </div>

            <div class="info-section">
                <h3><i class="fas fa-language"></i> Service Details</h3>
                <p>Type: ${data.service_type}</p>
                <p>Languages: ${data.source_language} → ${data.target_language}</p>
            </div>

            <div class="info-section">
                <h3><i class="fas fa-dollar-sign"></i> Payment Information</h3>
                <p>Rate: $${data.interpreter_rate}/hour</p>
                <p>Minimum Hours: ${data.minimum_hours}</p>
                <p>Estimated Total: $${calculateEstimatedTotal(data)}</p>
            </div>

            ${data.special_requirements ? `
                <div class="info-section">
                    <h3><i class="fas fa-exclamation-circle"></i> Special Requirements</h3>
                    <p>${data.special_requirements}</p>
                </div>
            ` : ''}

            ${data.notes ? `
                <div class="info-section">
                    <h3><i class="fas fa-sticky-note"></i> Notes</h3>
                    <p>${data.notes}</p>
                </div>
            ` : ''}
        </div>
    `;
}

// Fonctions utilitaires
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}"></i>
        ${message}
    `;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
    });
}

function calculateDuration(start, end) {
    const startDate = new Date(start);
    const endDate = new Date(end);
    const hours = (endDate - startDate) / (1000 * 60 * 60);
    return `${hours.toFixed(1)} hours`;
}

function calculateEstimatedTotal(assignment) {
    const startDate = new Date(assignment.start_time);
    const endDate = new Date(assignment.end_time);
    const hours = Math.max(
        assignment.minimum_hours,
        (endDate - startDate) / (1000 * 60 * 60)
    );
    return (hours * assignment.interpreter_rate).toFixed(2);
}