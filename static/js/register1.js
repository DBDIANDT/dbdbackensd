// register.js
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Lucide icons
    lucide.createIcons();

    // Password toggle functionality
    const togglePassword = document.getElementById('togglePassword');
    const passwordInput = document.getElementById('password');

    togglePassword.addEventListener('click', function() {
        const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
        passwordInput.setAttribute('type', type);
        this.dataset.lucide = type === 'password' ? 'eye' : 'eye-off';
        lucide.createIcons();
    });

    // Password strength checker
    const strengthBar = document.querySelector('.password-strength-bar');
    
    passwordInput.addEventListener('input', function() {
        const password = this.value;
        let strength = 0;
        const requirements = {
            length: password.length >= 8,
            number: /\d/.test(password),
            special: /[!@#$%^&*]/.test(password),
            uppercase: /[A-Z]/.test(password),
            lowercase: /[a-z]/.test(password)
        };

        Object.entries(requirements).forEach(([key, met]) => {
            const requirement = document.querySelector(`[data-requirement="${key}"]`);
            if (requirement) {
                if (met) {
                    requirement.classList.add('met');
                    strength += 20;
                } else {
                    requirement.classList.remove('met');
                }
            }
        });

        strengthBar.style.width = `${strength}%`;
        
        if (strength < 40) {
            strengthBar.style.background = 'var(--error-red)';
        } else if (strength < 80) {
            strengthBar.style.background = 'var(--warning-orange)';
        } else {
            strengthBar.style.background = 'var(--success-green)';
        }
    });

    // Real-time validation
    const inputs = document.querySelectorAll('.form-control');
    
    inputs.forEach(input => {
        input.addEventListener('input', function() {
            validateInput(this);
        });

        input.addEventListener('blur', function() {
            validateInput(this);
        });
    });

    function validateInput(input) {
        const validationMessage = input.parentElement.querySelector('.validation-message');
        
        switch(input.name) {
            case 'username':
                validateUsername(input, validationMessage);
                break;
            case 'email':
                validateEmail(input, validationMessage);
                break;
            case 'phone':
                validatePhone(input, validationMessage);
                break;
            case 'password2':
                validatePasswordConfirm(input, validationMessage);
                break;
        }
    }

    function validateUsername(input, messageElement) {
        if (input.value.length < 3) {
            showError(input, messageElement, 'Username must be at least 3 characters');
        } else if (!/^[a-zA-Z0-9_]+$/.test(input.value)) {
            showError(input, messageElement, 'Username can only contain letters, numbers and underscores');
        } else {
            showSuccess(input, messageElement);
        }
    }

    function validateEmail(input, messageElement) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(input.value)) {
            showError(input, messageElement, 'Please enter a valid email address');
        } else {
            showSuccess(input, messageElement);
        }
    }

    function validatePhone(input, messageElement) {
        const phoneRegex = /^\+?[\d\s-]{10,}$/;
        if (!phoneRegex.test(input.value)) {
            showError(input, messageElement, 'Please enter a valid phone number');
        } else {
            showSuccess(input, messageElement);
        }
    }

    function validatePasswordConfirm(input, messageElement) {
        if (input.value !== passwordInput.value) {
            showError(input, messageElement, 'Passwords do not match');
        } else {
            showSuccess(input, messageElement);
        }
    }

    function showError(input, messageElement, message) {
        input.classList.add('error');
        input.classList.remove('valid');
        messageElement.style.display = 'block';
        messageElement.textContent = message;
    }

    function showSuccess(input, messageElement) {
        input.classList.remove('error');
        input.classList.add('valid');
        messageElement.style.display = 'none';
    }
});