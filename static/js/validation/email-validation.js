/**
 * Функция валидации Email
 */
function validateEmail(input) {
    const emailPattern = /^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}$/;
    if (!emailPattern.test(input.value) && input.value !== '') {
        input.setCustomValidity('Пожалуйста, введите корректный email');
        return false;
    } else {
        input.setCustomValidity('');
        return true;
    }
}

/**
 * Инициализация валидации Email
 */
function initEmailValidation() {
    // Находим все поля Email и добавляем валидацию
    const emailInputs = document.querySelectorAll('input[name="e_mail"], input[type="email"]');
    emailInputs.forEach(function(input) {
        input.addEventListener('input', function() {
            validateEmail(this);
        });
        
        input.addEventListener('invalid', function(e) {
            if (this.value === '') {
                this.setCustomValidity('Пожалуйста, введите email');
            } else {
                validateEmail(this);
            }
        });
    });
}
