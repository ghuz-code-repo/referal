/**
 * Функция валидации PINFL (должен быть ровно 14 цифр)
 */
function validatePinfl(input) {
    const pinflPattern = /^\d{14}$/;
    if (!pinflPattern.test(input.value)) {
        input.setCustomValidity('ПИНФЛ должен содержать ровно 14 цифр');
        return false;
    } else {
        input.setCustomValidity('');
        return true;
    }
}

/**
 * Инициализация валидации ПИНФЛ
 */
function initPinflValidation() {
    // Находим все поля PINFL и добавляем валидацию
    const pinflInputs = document.querySelectorAll('input[name="pinfl"]');
    pinflInputs.forEach(function(input) {
        input.addEventListener('input', function() {
            // Удаляем все не-цифры
            this.value = this.value.replace(/\D/g, '');
            validatePinfl(this);
        });
        
        input.addEventListener('invalid', function(e) {
            if (this.value === '') {
                this.setCustomValidity('Пожалуйста, введите ПИНФЛ');
            } else {
                validatePinfl(this);
            }
        });
    });
}
