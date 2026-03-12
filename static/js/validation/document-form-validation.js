/**
 * Валидация формы редактирования документов реферала
 */
function initDocumentFormValidation() {
    console.log('Initializing document form validation...');
    
    // Инициализируем валидацию для всех модальных окон с документами
    document.addEventListener('click', function(e) {
        if (e.target.closest('[id^="DocumentFormModal_"]')) {
            const modal = e.target.closest('[id^="DocumentFormModal_"]');
            if (modal) {
                initModalValidation(modal);
            }
        }
    });
    
    // Также инициализируем для уже открытых модальных окон
    const modals = document.querySelectorAll('[id^="DocumentFormModal_"]');
    modals.forEach(modal => {
        initModalValidation(modal);
    });
}

/**
 * Инициализация валидации для конкретного модального окна
 */
function initModalValidation(modal) {
    const form = modal.querySelector('form');
    const nameInput = modal.querySelector('input[name="full_name"]');
    const phoneInput = modal.querySelector('input[name="phone_number"]');
    const passportInput = modal.querySelector('input[name="passport_number"]');
    
    if (!form) return;
    
    // Валидация ФИО
    if (nameInput) {
        nameInput.addEventListener('input', function(e) {
            validateFullNameInput(e.target);
        });
        
        nameInput.addEventListener('blur', function(e) {
            validateFullNameField(e.target);
        });
    }
    
    // Валидация телефона (используем существующую функцию)
    if (phoneInput) {
        phoneInput.addEventListener('input', function(e) {
            // Телефонная валидация уже инициализируется в phone-validation.js
        });
    }
    
    // Валидация паспорта
    if (passportInput) {
        passportInput.addEventListener('input', function(e) {
            validatePassportInput(e.target);
        });
        
        passportInput.addEventListener('blur', function(e) {
            validatePassportField(e.target);
        });
    }
    
    // Валидация формы при отправке
    form.addEventListener('submit', function(e) {
        if (!validateDocumentForm(form)) {
            e.preventDefault();
        }
    });
}

/**
 * Валидация ФИО в реальном времени
 */
function validateFullNameInput(field) {
    const value = field.value.trim();
    
    // Убираем предыдущие ошибки
    clearFieldValidationError(field);
    
    if (value.length > 0) {
        const words = value.split(/\s+/).filter(word => word.length > 0);
        
        if (words.length === 1 && words[0].length >= 2) {
            // Одно слово, но достаточной длины - предупреждение
            showFieldValidationWarning(field, 'Необходимо минимум 3 слова (Фамилия Имя Отчество)');
        } else if (words.length === 2 && words.every(word => word.length >= 2)) {
            // Два слова - предупреждение
            showFieldValidationWarning(field, 'Рекомендуется добавить отчество');
        } else if (words.length >= 3 && words.every(word => word.length >= 2)) {
            // Все хорошо
            field.classList.remove('error', 'warning');
            field.classList.add('success');
            setTimeout(() => field.classList.remove('success'), 1000);
        } else if (words.length > 0) {
            // Есть слова, но короткие
            showFieldValidationError(field, 'Каждое слово должно содержать минимум 2 символа');
        }
    }
}

/**
 * Полная валидация ФИО
 */
function validateFullNameField(field) {
    if (!field) return false;
    
    const value = field.value.trim();
    
    clearFieldValidationError(field);
    
    if (value === '') {
        showFieldValidationError(field, 'ФИО обязательно для заполнения');
        return false;
    }
    
    // Проверка на латиницу и минимум 3 слова (как в backend)
    if (!/^[A-Za-z`']+(?: [A-Za-z`']+){2,}$/.test(value)) {
        showFieldValidationError(field, 'ФИО должно содержать минимум 3 слова на латинице');
        return false;
    }
    
    // Проверка на двойные пробелы
    if (value.includes('  ')) {
        showFieldValidationError(field, 'Уберите лишние пробелы');
        return false;
    }
    
    field.classList.remove('error', 'warning');
    return true;
}

/**
 * Валидация паспорта в реальном времени
 */
function validatePassportInput(field) {
    const value = field.value.trim();
    
    clearFieldValidationError(field);
    
    if (value.length > 0) {
        // Формат: AA1234567 (2 буквы + 7 цифр)
        if (/^[A-Z]{2}\d{7}$/.test(value)) {
            field.classList.remove('error');
            field.classList.add('success');
            setTimeout(() => field.classList.remove('success'), 1000);
        } else if (value.length < 9) {
            // Пока вводит, не показываем ошибку
        } else {
            showFieldValidationError(field, 'Формат: AA1234567 (2 буквы + 7 цифр)');
        }
    }
}

/**
 * Полная валидация паспорта
 */
function validatePassportField(field) {
    if (!field) return true; // Паспорт не обязательный
    
    const value = field.value.trim();
    
    clearFieldValidationError(field);
    
    if (value === '') {
        return true; // Пустое поле допустимо
    }
    
    if (!/^[A-Z]{2}\d{7}$/.test(value)) {
        showFieldValidationError(field, 'Неверный формат паспорта. Используйте формат: AA1234567');
        return false;
    }
    
    field.classList.remove('error');
    return true;
}

/**
 * Валидация всей формы документов
 */
function validateDocumentForm(form) {
    const nameInput = form.querySelector('input[name="full_name"]');
    const phoneInput = form.querySelector('input[name="phone_number"]');
    const passportInput = form.querySelector('input[name="passport_number"]');
    
    let isValid = true;
    
    // Валидация ФИО
    if (nameInput && !validateFullNameField(nameInput)) {
        isValid = false;
    }
    
    // Валидация телефона (проверяем минимальную длину)
    if (phoneInput) {
        const phoneValue = phoneInput.value.trim();
        if (phoneValue && phoneValue.length < 13) { // +998 XX XXX XX XX = 13+ символов
            showFieldValidationError(phoneInput, 'Введите полный номер телефона');
            isValid = false;
        }
    }
    
    // Валидация паспорта
    if (passportInput && !validatePassportField(passportInput)) {
        isValid = false;
    }
    
    return isValid;
}

/**
 * Показать ошибку валидации поля
 */
function showFieldValidationError(field, message) {
    clearFieldValidationError(field);
    
    field.classList.add('error');
    
    const errorDiv = document.createElement('div');
    errorDiv.className = 'field-error-message';
    errorDiv.textContent = message;
    errorDiv.style.cssText = `
        color: #dc3545;
        font-size: 12px;
        margin-top: 2px;
        display: block;
    `;
    
    field.parentNode.appendChild(errorDiv);
}

/**
 * Показать предупреждение валидации поля
 */
function showFieldValidationWarning(field, message) {
    clearFieldValidationError(field);
    
    field.classList.add('warning');
    
    const warningDiv = document.createElement('div');
    warningDiv.className = 'field-warning-message';
    warningDiv.textContent = message;
    warningDiv.style.cssText = `
        color: #ffc107;
        font-size: 12px;
        margin-top: 2px;
        display: block;
    `;
    
    field.parentNode.appendChild(warningDiv);
}

/**
 * Очистить ошибки валидации поля
 */
function clearFieldValidationError(field) {
    field.classList.remove('error', 'warning', 'success');
    
    const errorMsg = field.parentNode.querySelector('.field-error-message');
    const warningMsg = field.parentNode.querySelector('.field-warning-message');
    
    if (errorMsg) errorMsg.remove();
    if (warningMsg) warningMsg.remove();
}

// Запускаем инициализацию при загрузке DOM
document.addEventListener('DOMContentLoaded', function() {
    initDocumentFormValidation();
});