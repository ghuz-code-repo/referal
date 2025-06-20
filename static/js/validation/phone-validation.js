/**
 * Функция форматирования телефона с поддержкой множественных номеров
 */
function formatPhone(input) {
    let value = input.value;
    
    // Split by comma to handle multiple phones
    let phones = value.split(',');
    let formattedPhones = [];
    
    for (let i = 0; i < phones.length; i++) {
        let phone = phones[i].trim();
        
        // Skip empty entries
        if (!phone) continue;
        
        // Всегда поддерживаем префикс для каждого номера
        if (!phone.startsWith('+998 ')) {
            phone = '+998 ' + phone.replace(/^\+998\s*/g, '');
        }
        
        // Получаем только цифры после префикса
        let digits = phone.substring(5).replace(/\D/g, '');
        
        // Ограничиваем до 9 цифр
        if (digits.length > 9) {
            digits = digits.substring(0, 9);
        }
        
        // Форматируем номер с пробелами: XX XXX XX XX
        let formatted = '';
        if (digits.length > 0) {
            formatted += digits.substring(0, Math.min(2, digits.length));
        }
        if (digits.length > 2) {
            formatted += ' ' + digits.substring(2, Math.min(5, digits.length));
        }
        if (digits.length > 5) {
            formatted += ' ' + digits.substring(5, Math.min(7, digits.length));
        }
        if (digits.length > 7) {
            formatted += ' ' + digits.substring(7, 9);
        }
        
        // Добавляем отформатированный номер
        if (formatted.trim()) {
            formattedPhones.push('+998 ' + formatted);
        }
    }
    
    // Обновляем значение поля ввода
    input.value = formattedPhones.join(', ');
}

/**
 * Инициализация валидации телефонов
 */
function initPhoneValidation() {
    // Находим все поля телефонов и добавляем форматирование
    const phoneInputs = document.querySelectorAll('input[name="phone"], input[name="phone_number"]');
    phoneInputs.forEach(function(input) {
        // Устанавливаем значение по умолчанию
        if (!input.value) {
            input.value = '+998 ';
        }
        
        input.addEventListener('input', function() {
            formatPhone(this);
        });
        
        input.addEventListener('focus', function() {
            if (this.value.length <= 5) {
                this.value = '+998 ';
                setTimeout(() => {
                    this.selectionStart = this.selectionEnd = 5;
                }, 0);
            }
        });
        
        // Проверка перед отправкой формы с поддержкой множественных номеров
        if (input.form) {
            input.form.addEventListener('submit', function(e) {
                const phones = input.value.split(',');
                let allValid = true;
                
                for (let phone of phones) {
                    phone = phone.trim();
                    if (!phone) continue;
                    
                    const digits = phone.substring(5).replace(/\D/g, '');
                    if (digits.length !== 9) {
                        allValid = false;
                        break;
                    }
                }
                
                if (!allValid) {
                    alert('Пожалуйста, введите 9 цифр для каждого номера телефона после кода страны. Для множественных номеров разделяйте их запятыми.');
                    e.preventDefault();
                }
            });
        }
    });
}
