document.addEventListener('DOMContentLoaded', function() {
    // Variables pour le multi-étapes
    let currentStep = 1;
    const totalSteps = 3;
    
    // Éléments du DOM
    const form = document.querySelector('#registrationForm');
    const steps = document.querySelectorAll('.registration-step');
    const progressBar = document.querySelector('.progress-bar-fill');
    const stepCircles = document.querySelectorAll('.step-circle');
    const nextButtons = document.querySelectorAll('.btn-next');
    const prevButtons = document.querySelectorAll('.btn-prev');
    const submitButton = document.querySelector('.btn-submit');

    // Mise à jour de la barre de progression
    function updateProgress() {
        const progress = ((currentStep - 1) / (totalSteps - 1)) * 100;
        progressBar.style.width = `${progress}%`;

        // Mise à jour des cercles d'étape
        stepCircles.forEach((circle, index) => {
            if (index + 1 < currentStep) {
                circle.classList.add('completed');
                circle.innerHTML = '✓';
            } else if (index + 1 === currentStep) {
                circle.classList.add('active');
                circle.classList.remove('completed');
                circle.innerHTML = index + 1;
            } else {
                circle.classList.remove('active', 'completed');
                circle.innerHTML = index + 1;
            }
        });
    }

    // Afficher l'étape actuelle
    function showStep(stepNumber) {
        steps.forEach((step, index) => {
            if (index + 1 === stepNumber) {
                step.classList.add('active');
                step.style.display = 'block';
                step.classList.add('fade-in');
            } else {
                step.classList.remove('active');
                step.style.display = 'none';
                step.classList.remove('fade-in');
            }
        });
        updateProgress();
    }

    // Validation des champs par étape
    function validateStep(step) {
        const activeStep = document.querySelector(`.registration-step[data-step="${step}"]`);
        const inputs = activeStep.querySelectorAll('input, select, textarea');
        let isValid = true;

        inputs.forEach(input => {
            // Réinitialiser les messages d'erreur précédents
            removeError(input);

            if (input.hasAttribute('required') && !input.value.trim()) {
                showError(input, 'This field is required');
                isValid = false;
            } else if (input.type === 'email' && input.value) {
                if (!validateEmail(input.value)) {
                    showError(input, 'Please enter a valid email address');
                    isValid = false;
                }
            } else if (input.id === 'password') {
                if (!validatePassword(input.value)) {
                    showError(input, 'Password must be at least 8 characters long');
                    isValid = false;
                }
            } else if (input.id === 'confirmPassword') {
                const password = document.querySelector('#password').value;
                if (input.value !== password) {
                    showError(input, 'Passwords do not match');
                    isValid = false;
                }
            }
        });

        return isValid;
    }

    // Afficher les messages d'erreur
    function showError(input, message) {
        const formGroup = input.closest('.form-group');
        const error = document.createElement('div');
        error.className = 'error-message';
        error.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
        formGroup.appendChild(error);
        input.classList.add('error');
    }

    // Supprimer les messages d'erreur
    function removeError(input) {
        const formGroup = input.closest('.form-group');
        const error = formGroup.querySelector('.error-message');
        if (error) {
            error.remove();
        }
        input.classList.remove('error');
    }

    // Validation d'email
    function validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(String(email).toLowerCase());
    }

    // Validation de mot de passe
    function validatePassword(password) {
        return password.length >= 8;
    }

    // Gestionnaires d'événements pour les boutons suivant/précédent
    nextButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            e.preventDefault();
            if (validateStep(currentStep)) {
                currentStep++;
                showStep(currentStep);
            }
        });
    });

    prevButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            e.preventDefault();
            currentStep--;
            showStep(currentStep);
        });
    });

    // Gestion de la soumission du formulaire
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (validateStep(currentStep)) {
                const formData = new FormData(form);
                
                try {
                    const response = await fetch(form.action, {
                        method: 'POST',
                        body: formData,
                        headers: {
                            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                        }
                    });

                    if (response.ok) {
                        showSuccessMessage('Registration successful! Please check your email for verification.');
                        // Redirection après succès
                        setTimeout(() => {
                            window.location.href = response.url || '/registration-success/';
                        }, 2000);
                    } else {
                        const data = await response.json();
                        showErrorMessage(data.error || 'An error occurred during registration.');
                    }
                } catch (error) {
                    showErrorMessage('Network error. Please try again.');
                }
            }
        });
    }

    // Afficher un message de succès
    function showSuccessMessage(message) {
        const alert = document.createElement('div');
        alert.className = 'alert alert-success';
        alert.innerHTML = message;
        form.insertBefore(alert, form.firstChild);
    }

    // Afficher un message d'erreur
    function showErrorMessage(message) {
        const alert = document.createElement('div');
        alert.className = 'alert alert-error';
        alert.innerHTML = message;
        form.insertBefore(alert, form.firstChild);
    }

    // Animations de transition
    const inputs = document.querySelectorAll('.form-control');
    inputs.forEach(input => {
        input.addEventListener('focus', () => {
            input.closest('.form-group').classList.add('focused');
        });

        input.addEventListener('blur', () => {
            if (!input.value) {
                input.closest('.form-group').classList.remove('focused');
            }
        });
    });

    // Initialisation
    showStep(1);
});