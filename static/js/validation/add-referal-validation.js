/**
 * Улучшенная валидация формы добавления реферала
 * Требования:
 * - ФИО: только латиница, минимум 2 слова, каждое с большой буквы
 * - Телефон: формат +998 XX XXX XX XX
 * - Кнопка неактивна пока поля не заполнены правильно
 * - Ошибки показываются красным шрифтом рядом с лейблами
 */

function initAddReferalValidation() {
    console.log('🔧 Initializing enhanced add referal validation...');
    
    const form = document.querySelector('#add-referal-form') || document.querySelector('.add-referal-form');
    
    if (!form) {
        console.log('Add referal form not found');
        return;
    }
    
    const phoneInput = form.querySelector('#phone_number') || form.querySelector('[name="phone"]');
    const nameInput = form.querySelector('#full_name') || form.querySelector('[name="full_name"]');
    const submitBtn = form.querySelector('#save-referal-btn') || form.querySelector('.save-all-btn');
    
    if (!phoneInput || !nameInput || !submitBtn) {
        console.log('Add referal form elements not found');
        return;
    }
    
    // Функция обновления состояния кнопки
    function updateSubmitButton() {
        const isNameValid = validateNameField(nameInput, true); // silent validation
        const isPhoneValid = validatePhoneField(phoneInput, true); // silent validation
        
        if (isNameValid && isPhoneValid) {
            submitBtn.disabled = false;
            submitBtn.classList.remove('disabled');
        } else {
            submitBtn.disabled = true;
            submitBtn.classList.add('disabled');
        }
    }
    
    // Валидация имени в реальном времени
    nameInput.addEventListener('input', function(e) {
        validateNameInput(e.target);
        updateSubmitButton();
    });
    
    nameInput.addEventListener('blur', function(e) {
        validateNameField(e.target);
        updateSubmitButton();
    });
    
    // Валидация телефона в реальном времени
    phoneInput.addEventListener('input', function(e) {
        validatePhoneInput(e.target);
        updateSubmitButton();
    });
    
    phoneInput.addEventListener('blur', function(e) {
        validatePhoneField(e.target);
        updateSubmitButton();
    });
    
    // Валидация формы при отправке
    form.addEventListener('submit', function(e) {
        if (!validateAddReferalForm()) {
            e.preventDefault();
        }
    });
    
    // Первоначальная проверка состояния кнопки
    updateSubmitButton();
}

/**
 * Валидация поля имени в реальном времени
 */
function validateNameInput(field) {
    const value = field.value.trim();
    
    // Убираем предыдущие ошибки
    clearValidationError(field);
    
    if (value.length > 0) {
        // Проверяем количество слов
        const words = value.split(/\s+/).filter(word => word.length > 0);
        if (words.length < 2) {
            field.classList.add('error');
            showInlineError('name-error', 'Минимум 2 слова');
            return false;
        }
        
        // Всё правильно
        field.classList.remove('error');
        field.classList.add('success');
        clearInlineError('name-error');
        return true;
    }
    
    return false;
}

/**
 * Полная валидация поля имени
 */
function validateNameField(field, silent = false) {
    if (!field) {
        console.error('Name field is null');
        return false;
    }
    
    const value = field.value.trim();
    
    if (!silent) {
        clearValidationError(field);
        clearInlineError('name-error');
    }
    
    if (value === '') {
        if (!silent) {
            field.classList.add('error');
            showInlineError('name-error', 'ФИО обязательно');
        }
        return false;
    }
    
    if (value.length < 3) {
        if (!silent) {
            field.classList.add('error');
            showInlineError('name-error', 'Минимум 3 символа');
        }
        return false;
    }
    
    // Проверяем минимум 2 слова
    const words = value.split(/\s+/).filter(word => word.length > 0);
    if (words.length < 2) {
        if (!silent) {
            field.classList.add('error');
            showInlineError('name-error', 'Минимум 2 слова');
        }
        return false;
    }
    
    if (!silent) {
        field.classList.remove('error');
        clearInlineError('name-error');
    }
    return true;
}

/**
 * Валидация поля телефона в реальном времени
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
    clearInlineError('phone-error');
    
    if (value.length > 0) {
        // Проверяем базовый формат
        if (!value.startsWith('+998')) {
            field.classList.add('error');
            showInlineError('phone-error', 'Должен начинаться с +998');
            return false;
        }
        
        // Проверяем полный формат
        const cleanPhone = value.replace(/\s/g, '');
        if (cleanPhone.length < 13) {
            field.classList.add('error');
            showInlineError('phone-error', 'Неполный номер');
            return false;
        }
        
        const isValid = /^\+998\d{9}$/.test(cleanPhone);
        if (isValid) {
            field.classList.remove('error');
            field.classList.add('success');
            clearInlineError('phone-error');
            return true;
        } else {
            field.classList.add('error');
            showInlineError('phone-error', 'Неверный формат');
            return false;
        }
    }
    
    return false;
}

/**
 * Полная валидация поля телефона
 */
function validatePhoneField(field, silent = false) {
    if (!field) {
        console.error('Phone field is null');
        return false;
    }
    
    const value = field.value.trim();
    
    if (!silent) {
        clearValidationError(field);
        clearInlineError('phone-error');
    }
    
    if (value === '') {
        if (!silent) {
            field.classList.add('error');
            showInlineError('phone-error', 'Телефон обязателен');
        }
        return false;
    }
    
    if (!value.startsWith('+998')) {
        if (!silent) {
            field.classList.add('error');
            showInlineError('phone-error', 'Должен начинаться с +998');
        }
        return false;
    }
    
    const cleanPhone = value.replace(/\s/g, '');
    const phonePattern = /^\+998\d{9}$/;
    
    if (!phonePattern.test(cleanPhone)) {
        if (!silent) {
            field.classList.add('error');
            showInlineError('phone-error', 'Формат: +998 XX XXX XX XX');
        }
        return false;
    }
    
    if (!silent) {
        field.classList.remove('error');
        clearInlineError('phone-error');
    }
    return true;
}

/**
 * Валидация всей формы
 */
function validateAddReferalForm(form) {
    // If form is not provided, try to find it
    if (!form) {
        form = document.querySelector('#add-referal-form') || document.querySelector('.add-referal-form');
    }
    
    if (!form) {
        console.error('Add referal form not found');
        return false;
    }
    
    const nameField = form.querySelector('#full_name') || form.querySelector('[name="full_name"]');
    const phoneField = form.querySelector('#phone_number') || form.querySelector('[name="phone"]');
    
    let isValid = true;
    
    if (!nameField) {
        console.error('Name field not found');
        return false;
    }
    
    if (!phoneField) {
        console.error('Phone field not found');
        return false;
    }
    
    if (!validateNameField(nameField)) {
        isValid = false;
    }
    
    if (!validatePhoneField(phoneField)) {
        isValid = false;
    }
    
    return isValid;
}

/**
 * Показать инлайн ошибку в лейбле
 */
function showInlineError(errorId, message) {
    const errorElement = document.getElementById(errorId);
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'inline';
    }
}

/**
 * Очистить инлайн ошибку в лейбле
 */
function clearInlineError(errorId) {
    const errorElement = document.getElementById(errorId);
    if (errorElement) {
        errorElement.textContent = '';
        errorElement.style.display = 'none';
    }
}

/**
 * Показать ошибку валидации (старый метод, оставлен для совместимости)
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
 * Убрать ошибки валидации (старый метод, оставлен для совместимости)
 */
function clearValidationError(field) {
    field.classList.remove('error', 'success');
    const errorDiv = field.parentElement.querySelector('.validation-error');
    if (errorDiv) {
        errorDiv.remove();
    }
}

// Инициализация при загрузке DOM
document.addEventListener('DOMContentLoaded', function() {
    initAddReferalValidation();
});

// Инициализация при открытии модального окна
document.addEventListener('click', function(e) {
    // Если кликнули по кнопке открытия модалки добавления реферала
    if (e.target && (e.target.matches('[data-action="add-referal"]') || e.target.closest('[data-action="add-referal"]'))) {
        setTimeout(() => {
            initAddReferalValidation();
        }, 100);
    }
});