/**
 * Валидация формы добавления реферала
 */
function initAddReferalValidation() {
    console.log('Initializing add referal validation...');
    
    const form = document.querySelector('.add-referal-form');
    const phoneInput = document.querySelector('#phone_number');
    const nameInput = document.querySelector('#full_name');
    
    if (!form || !phoneInput || !nameInput) {
        console.log('Add referal form elements not found');
        return;
    }
    
    // Валидация телефона
    phoneInput.addEventListener('input', function(e) {
        validatePhoneInput(e.target);
    });
    
    phoneInput.addEventListener('blur', function(e) {
        validatePhoneField(e.target);
    });
    
    // Валидация имени
    nameInput.addEventListener('input', function(e) {
        validateNameInput(e.target);
    });
    
    nameInput.addEventListener('blur', function(e) {
        validateNameField(e.target);
    }); 
    
    // Валидация формы при отправке
    form.addEventListener('submit', function(e) {
        if (!validateAddReferalForm()) {
            e.preventDefault();
        }
    });
}

/**
 * Валидация поля имени
 */
function validateNameInput(field) {
    const value = field.value.trim();
    
    // Убираем предыдущие ошибки
    clearValidationError(field);
    
    if (value.length > 0 && value.length < 2) {
        field.classList.add('error');
    } else if (value.length >= 2) {
        field.classList.remove('error');
        field.classList.add('success');
        setTimeout(() => field.classList.remove('success'), 1000);
    }
}

/**
 * Полная валидация поля имени
 */
function validateNameField(field) {
    const value = field.value.trim();
    
    clearValidationError(field);
    
    if (value === '') {
        showValidationError(field, 'Имя реферала обязательно для заполнения');
        return false;
    }
    
    if (value.length < 2) {
        showValidationError(field, 'Имя должно содержать минимум 2 символа');
        return false;
    }
    
    if (!/^[а-яёА-ЯЁa-zA-Z\s\-']+$/u.test(value)) {
        showValidationError(field, 'Имя может содержать только буквы, пробелы и дефисы');
        return false;
    }
    
    field.classList.remove('error');
    return true;
}

/**
 * Валидация поля телефона
 */
function validatePhoneInput(field) {
    let value = field.value;
    
    // Автоматическое форматирование
    if (value && !value.startsWith('+998')) {
        if (value.startsWith('998')) {
            value = '+' + value;
        } else if (value.startsWith('8') && value.length > 1) {
            value = '+998' + value.substring(1);
        } else if (/^\d/.test(value) && !value.startsWith('998')) {
            value = '+998' + value;
        }
        field.value = value;
    }
    
    clearValidationError(field);
    
    if (value.length > 0) {
        const isValid = /^\+998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}$/.test(value.replace(/\s/g, ''));
        if (isValid) {
            field.classList.remove('error');
            field.classList.add('success');
            setTimeout(() => field.classList.remove('success'), 1000);
        } else {
            field.classList.add('error');
        }
    }
}

/**
 * Полная валидация поля телефона
 */
function validatePhoneField(field) {
    const value = field.value.trim();
    
    clearValidationError(field);
    
    if (value === '') {
        showValidationError(field, 'Номер телефона обязателен для заполнения');
        return false;
    }
    
    const phonePattern = /^\+998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}$/;
    if (!phonePattern.test(value)) {
        showValidationError(field, 'Неверный формат телефона. Используйте: +998 XX XXX XX XX');
        return false;
    }
    
    field.classList.remove('error');
    return true;
}

/**
 * Валидация всей формы
 */
function validateAddReferalForm() {
    const nameField = document.querySelector('#full_name');
    const phoneField = document.querySelector('#phone_number');
    
    let isValid = true;
    
    if (!validateNameField(nameField)) {
        isValid = false;
    }
    
    if (!validatePhoneField(phoneField)) {
        isValid = false;
    }
    
    return isValid;
}

/**
 * Показать ошибку валидации
 */
function showValidationError(field, message) {
    clearValidationError(field);
    
    field.classList.add('error');
    
    const errorDiv = document.createElement('div');
    errorDiv.className = 'validation-error';
    errorDiv.textContent = message;
    
    field.parentElement.appendChild(errorDiv);
}

/**
 * Убрать ошибки валидации
 */
function clearValidationError(field) {
    field.classList.remove('error', 'success');
    const errorDiv = field.parentElement.querySelector('.validation-error');
    if (errorDiv) {
        errorDiv.remove();
    }
}
