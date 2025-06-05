// clientregister.js

document.addEventListener('DOMContentLoaded', () => {
    // Sélecteurs des éléments
    const form = document.querySelector('.auth-form');
    const inputs = document.querySelectorAll('.form-control');
    const passwordInput = document.querySelector('input[name="password1"]');
    const confirmPasswordInput = document.querySelector('input[name="password2"]');
    const progressLine = document.querySelector('.progress-line-active');
    
    // Configuration de la force du mot de passe
    const passwordStrengthConfig = {
        minLength: 8,
        requireNumbers: true,
        requireSymbols: true,
        requireUppercase: true,
        requireLowercase: true
    };

    // Initialisation de la barre de progression
    const initializeProgress = () => {
        if (progressLine) {
            progressLine.style.width = '50%';
        }
    };

    // Validation en temps réel des champs
    const validateInput = (input) => {
        const value = input.value.trim();
        
        // Réinitialisation des classes
        input.classList.remove('is-valid', 'is-invalid');
        
        // Validation spécifique selon le type de champ
        switch(input.name) {
            case 'email':
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (emailRegex.test(value)) {
                    input.classList.add('is-valid');
                } else if (value) {
                    input.classList.add('is-invalid');
                }
                break;

            case 'phone':
                const phoneRegex = /^[\d\s+()-]{10,}$/;
                if (phoneRegex.test(value)) {
                    input.classList.add('is-valid');
                } else if (value) {
                    input.classList.add('is-invalid');
                }
                break;

            case 'password1':
                updatePasswordStrength(value);
                break;

            case 'password2':
                if (value === passwordInput.value && value) {
                    input.classList.add('is-valid');
                } else if (value) {
                    input.classList.add('is-invalid');
                }
                break;

            default:
                if (value.length > 2) {
                    input.classList.add('is-valid');
                } else if (value) {
                    input.classList.add('is-invalid');
                }
        }
    };

    // Vérification de la force du mot de passe
    const calculatePasswordStrength = (password) => {
        let strength = 0;
        
        if (password.length >= passwordStrengthConfig.minLength) strength++;
        if (/[0-9]/.test(password) && passwordStrengthConfig.requireNumbers) strength++;
        if (/[!@#$%^&*]/.test(password) && passwordStrengthConfig.requireSymbols) strength++;
        if (/[A-Z]/.test(password) && passwordStrengthConfig.requireUppercase) strength++;
        if (/[a-z]/.test(password) && passwordStrengthConfig.requireLowercase) strength++;

        return (strength / 5) * 100;
    };

    // Mise à jour visuelle de la force du mot de passe
    const updatePasswordStrength = (password) => {
        const strength = calculatePasswordStrength(password);
        const strengthMeter = document.querySelector('.strength-meter-fill');
        const strengthText = document.querySelector('.strength-text');

        if (strengthMeter) {
            strengthMeter.style.width = `${strength}%`;
            
            if (strength < 40) {
                strengthMeter.style.backgroundColor = 'var(--error-red)';
                strengthText.textContent = 'Weak password';
            } else if (strength < 80) {
                strengthMeter.style.backgroundColor = 'var(--warning-orange)';
                strengthText.textContent = 'Moderate password';
            } else {
                strengthMeter.style.backgroundColor = 'var(--success-green)';
                strengthText.textContent = 'Strong password';
            }
        }
    };

    // Gestion de la visibilité du mot de passe
    const setupPasswordToggle = () => {
        const toggleButtons = document.querySelectorAll('.password-toggle');
        
        toggleButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const input = e.target.closest('.form-group').querySelector('input');
                const type = input.type === 'password' ? 'text' : 'password';
                input.type = type;
                
                // Mise à jour de l'icône
                e.target.innerHTML = type === 'password' ? '👁' : '👁️‍🗨️';
            });
        });
    };

    // Sauvegarde automatique des données du formulaire
    const setupAutoSave = () => {
        let autoSaveTimeout;

        const saveFormData = () => {
            const formData = {};
            inputs.forEach(input => {
                if (input.name !== 'password1' && input.name !== 'password2') {
                    formData[input.name] = input.value;
                }
            });
            localStorage.setItem('registrationFormData', JSON.stringify(formData));
        };

        inputs.forEach(input => {
            if (input.name !== 'password1' && input.name !== 'password2') {
                input.addEventListener('input', () => {
                    clearTimeout(autoSaveTimeout);
                    autoSaveTimeout = setTimeout(saveFormData, 1000);
                });
            }
        });

        // Restauration des données sauvegardées
        const savedData = localStorage.getItem('registrationFormData');
        if (savedData) {
            const formData = JSON.parse(savedData);
            Object.keys(formData).forEach(key => {
                const input = document.querySelector(`[name="${key}"]`);
                if (input) {
                    input.value = formData[key];
                    validateInput(input);
                }
            });
        }
    };

    // Gestionnaires d'événements
    const setupEventListeners = () => {
        inputs.forEach(input => {
            input.addEventListener('input', () => validateInput(input));
            input.addEventListener('blur', () => validateInput(input));
        });

        form.addEventListener('submit', (e) => {
            let isValid = true;
            inputs.forEach(input => {
                validateInput(input);
                if (input.classList.contains('is-invalid')) {
                    isValid = false;
                }
            });

            if (!isValid) {
                e.preventDefault();
                const firstInvalid = form.querySelector('.is-invalid');
                if (firstInvalid) {
                    firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            } else {
                localStorage.removeItem('registrationFormData');
            }
        });
    };

    // Initialisation
    const init = () => {
        initializeProgress();
        setupPasswordToggle();
        setupAutoSave();
        setupEventListeners();
    };

    init();
});