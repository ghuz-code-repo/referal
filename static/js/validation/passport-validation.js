/**
 * Валидация паспортных данных
 */

// Карта сопоставления русских букв с английскими
const russianToEnglishMap = {
    'й': 'Q', 'ц': 'W', 'у': 'E', 'к': 'R', 'е': 'T', 'н': 'Y', 'г': 'U', 'ш': 'I', 'щ': 'O', 'з': 'P',
    'х': '[', 'ъ': ']', 'ф': 'A', 'ы': 'S', 'в': 'D', 'а': 'F', 'п': 'G', 'р': 'H', 'о': 'J', 'л': 'K',
    'д': 'L', 'ж': ';', 'э': "'", 'я': 'Z', 'ч': 'X', 'с': 'C', 'м': 'V', 'и': 'B', 'т': 'N', 'ь': 'M',
    'б': ',', 'ю': '.', 'Й': 'Q', 'Ц': 'W', 'У': 'E', 'К': 'R', 'Е': 'T', 'Н': 'Y', 'Г': 'U', 'Ш': 'I',
    'Щ': 'O', 'З': 'P', 'Х': '[', 'Ъ': ']', 'Ф': 'A', 'Ы': 'S', 'В': 'D', 'А': 'F', 'П': 'G', 'Р': 'H',
    'О': 'J', 'Л': 'K', 'Д': 'L', 'Ж': ';', 'Э': "'", 'Я': 'Z', 'Ч': 'X', 'С': 'C', 'М': 'V', 'И': 'B',
    'Т': 'N', 'Ь': 'M', 'Б': ',', 'Ю': '.'
};

function initPassportValidation() {
    console.log('Initializing passport validation...');
    
    // Находим все поля паспортных данных
    const passportFields = document.querySelectorAll('input[name="passport_number"]');
    
    passportFields.forEach(field => {
        // Обработка ввода в реальном времени
        field.addEventListener('input', function(e) {
            validatePassportInput(e.target);
        });
        
        // Обработка потери фокуса
        field.addEventListener('blur', function(e) {
            validatePassportField(e.target);
        });
        
        // Предотвращение ввода недопустимых символов с конвертацией раскладки
        field.addEventListener('keypress', function(e) {
            const start = e.target.selectionStart;
            const end = e.target.selectionEnd;
            const currentValue = e.target.value;
            const selectedLength = end - start;
            
            // Вычисляем длину после замены выделенного текста
            const newLength = currentValue.length - selectedLength + 1;
            
            // Проверяем длину - максимум 9 символов (учитывая замену выделенного текста)
            if (newLength > 9) {
                e.preventDefault();
                return;
            }
            
            // Проверяем, является ли символ русской буквой
            if (russianToEnglishMap[e.key]) {
                e.preventDefault();
                // Вставляем английскую букву вместо русской
                const englishChar = russianToEnglishMap[e.key];
                // Определяем позицию для проверки (начало выделения)
                if (isValidPassportCharAtPosition(englishChar, start)) {
                    insertCharAtCursor(e.target, englishChar);
                    validatePassportInput(e.target);
                }
                return;
            }
            
            // Определяем позицию для проверки (начало выделения)
            if (!isValidPassportCharAtPosition(e.key, start)) {
                e.preventDefault();
            }
        });
        
        // Обработка вставки текста
        field.addEventListener('paste', function(e) {
            e.preventDefault();
            const pastedText = (e.clipboardData || window.clipboardData).getData('text');
            const cleanedText = cleanPassportText(pastedText);
            e.target.value = cleanedText;
            validatePassportField(e.target);
        });
    });
}

/**
 * Вставляет символ в текущую позицию курсора (с учетом выделенного текста)
 */
function insertCharAtCursor(input, char) {
    const start = input.selectionStart;
    const end = input.selectionEnd;
    const value = input.value;
    const selectedLength = end - start;
    
    // Вычисляем длину после замены выделенного текста
    const newLength = value.length - selectedLength + 1;
    
    // Проверяем, что не превышаем максимальную длину после замены
    if (newLength > 9) {
        return;
    }
    
    // Заменяем выделенный текст новым символом
    input.value = value.substring(0, start) + char + value.substring(end);
    input.setSelectionRange(start + 1, start + 1);
}

/**
 * Проверяет, является ли символ допустимым для паспорта в определенной позиции
 */
function isValidPassportCharAtPosition(char, position) {
    // Разрешаем служебные клавиши
    const allowedKeys = ['Backspace', 'Delete', 'Tab', 'Enter', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'];
    if (allowedKeys.includes(char)) {
        return true;
    }
    
    // Первые две позиции - только буквы
    if (position < 2) {
        return /^[A-Za-z]$/.test(char);
    }
    
    // Позиции с 3 по 9 - только цифры
    if (position >= 2 && position < 9) {
        return /^[0-9]$/.test(char);
    }
    
    // Позиция 9 и выше - запрещено
    return false;
}

/**
 * Очищает текст от недопустимых символов, конвертирует русские буквы и приводит к правильному формату
 */
function cleanPassportText(text) {
    let cleanedText = '';
    
    for (let i = 0; i < text.length && cleanedText.length < 9; i++) {
        const char = text[i];
        
        // Если это русская буква, конвертируем в английскую
        if (russianToEnglishMap[char]) {
            const englishChar = russianToEnglishMap[char];
            if (isValidPassportCharAtPosition(englishChar, cleanedText.length)) {
                cleanedText += englishChar;
            }
        }
        // Если это английская буква или цифра, проверяем позицию
        else if (/^[A-Za-z0-9]$/.test(char)) {
            if (isValidPassportCharAtPosition(char, cleanedText.length)) {
                cleanedText += char.toUpperCase();
            }
        }
        // Все остальные символы игнорируем
    }
    
    return cleanedText;
}

/**
 * Валидирует ввод паспорта в реальном времени
 */
function validatePassportInput(field) {
    const originalValue = field.value;
    const cleanedValue = cleanPassportText(originalValue);
    
    // Обновляем значение поля если оно изменилось
    if (originalValue !== cleanedValue) {
        // Сохраняем информацию о выделении
        const start = field.selectionStart;
        const end = field.selectionEnd;
        const wasSelected = start !== end;
        
        field.value = cleanedValue;
        
        // Если текст был выделен, ставим курсор в конец очищенного текста
        if (wasSelected) {
            field.setSelectionRange(cleanedValue.length, cleanedValue.length);
        } else {
            // Пытаемся сохранить позицию курсора
            const newPosition = Math.min(start, cleanedValue.length);
            field.setSelectionRange(newPosition, newPosition);
        }
    }
    
    // Убираем предыдущие ошибки
    clearFieldError(field);
    
    // Показываем промежуточную валидацию
    const value = field.value;
    if (value.length > 0) {
        if (value.length < 2) {
            // Пока введены не все буквы
            field.classList.remove('error', 'success');
        } else if (value.length === 2) {
            // Введены 2 буквы, проверяем что это действительно буквы
            if (/^[A-Z]{2}$/.test(value)) {
                field.classList.remove('error');
                field.classList.add('partial-success');
            } else {
                field.classList.add('error');
                field.classList.remove('partial-success');
            }
        } else if (value.length > 2 && value.length < 9) {
            // Введены буквы и часть цифр
            if (/^[A-Z]{2}[0-9]+$/.test(value)) {
                field.classList.remove('error');
                field.classList.add('partial-success');
            } else {
                field.classList.add('error');
                field.classList.remove('partial-success');
            }
        }
    }
}

/**
 * Полная валидация поля паспорта
 */
function validatePassportField(field) {
    const value = field.value.trim();
    
    // Убираем предыдущие ошибки
    clearFieldError(field);
    field.classList.remove('partial-success');
    
    if (value === '') {
        return true; // Пустое поле может быть валидным если не обязательное
    }
    
    // Проверяем максимальную длину
    if (value.length > 9) {
        showFieldError(field, 'Паспорт не может содержать более 9 символов');
        return false;
    }
    
    // Проверяем минимальную длину для полного паспорта
    if (value.length > 0 && value.length < 9) {
        showFieldError(field, 'Неполный номер паспорта. Должно быть: 2 буквы + 7 цифр');
        return false;
    }
    
    // Проверяем формат паспорта (2 буквы + 7 цифр)
    const passportPattern = /^[A-Z]{2}[0-9]{7}$/;
    
    if (!passportPattern.test(value)) {
        showFieldError(field, 'Неверный формат паспорта. Должно быть: 2 заглавные буквы + 7 цифр (например: AA1234567)');
        return false;
    }
    
    showFieldSuccess(field);
    return true;
}

/**
 * Показывает ошибку валидации
 */
function showFieldError(field, message) {
    clearFieldError(field);
    
    field.classList.add('error');
    
    const errorDiv = document.createElement('div');
    errorDiv.className = 'field-error';
    errorDiv.textContent = message;
    
    field.parentElement.style.position = 'relative';
    field.parentElement.appendChild(errorDiv);
}

/**
 * Показывает успешную валидацию
 */
function showFieldSuccess(field) {
    field.classList.remove('error', 'partial-success');
    field.classList.add('success');
    setTimeout(() => {
        field.classList.remove('success');
    }, 2000);
}

/**
 * Убирает ошибки валидации
 */
function clearFieldError(field) {
    field.classList.remove('error');
    const errorDiv = field.parentElement.querySelector('.field-error');
    if (errorDiv) {
        errorDiv.remove();
    }
}

/**
 * Валидирует все поля паспорта на форме
 */
function validateAllPassportFields() {
    const passportFields = document.querySelectorAll('input[name="passport_number"]');
    let allValid = true;
    
    passportFields.forEach(field => {
        if (!validatePassportField(field)) {
            allValid = false;
        }
    });
    
    return allValid;
}
