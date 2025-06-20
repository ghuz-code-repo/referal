document.addEventListener('DOMContentLoaded', function() {
    const cardInput = document.getElementById('card_number');
    
    if (cardInput) {
        cardInput.addEventListener('input', function(e) {
            let value = this.value.replace(/\s/g, ''); // Убираем пробелы
            value = value.replace(/[^0-9]/g, ''); // Оставляем только цифры
            
            // Ограничиваем до 16 цифр
            if (value.length > 16) {
                value = value.slice(0, 16);
            }
            
            // Форматируем с пробелами (xxxx xxxx xxxx xxxx)
            const formattedValue = value.replace(/(.{4})/g, '$1 ').trim();
            
            this.value = formattedValue;
            validateCard(this);
        });
        
        cardInput.addEventListener('blur', function() {
            validateCard(this);
        });
        
        // Обработка клавиш Backspace и Delete
        cardInput.addEventListener('keydown', function(e) {
            // Разрешаем навигационные клавиши
            if ([8, 9, 27, 13, 46].indexOf(e.keyCode) !== -1 ||
                // Разрешаем Ctrl+A, Ctrl+C, Ctrl+V, Ctrl+X
                (e.keyCode === 65 && e.ctrlKey === true) ||
                (e.keyCode === 67 && e.ctrlKey === true) ||
                (e.keyCode === 86 && e.ctrlKey === true) ||
                (e.keyCode === 88 && e.ctrlKey === true) ||
                // Разрешаем стрелки
                (e.keyCode >= 35 && e.keyCode <= 39)) {
                return;
            }
            
            // Убеждаемся, что это цифра
            if ((e.shiftKey || (e.keyCode < 48 || e.keyCode > 57)) && (e.keyCode < 96 || e.keyCode > 105)) {
                e.preventDefault();
            }
        });
    }
    
    function validateCard(input) {
        const value = input.value.replace(/\s/g, ''); // Убираем пробелы для валидации
        
        clearValidationError(input);
        
        if (value === '') {
            return true; // Поле не обязательное
        }
        
        if (value.length < 16) {
            showValidationError(input, 'Номер карты должен содержать 16 цифр');
            return false;
        }
        
        // Проверяем алгоритм Луна
        if (!luhnCheck(value)) {
            showValidationError(input, 'Неверный номер карты');
            return false;
        }
        
        // Определяем тип карты
        const cardType = getCardType(value);
        if (cardType) {
            showValidationSuccess(input, `Карта ${cardType}`);
        } else {
            showValidationSuccess(input);
        }
        
        return true;
    }
    
    // Алгоритм Луна для проверки номера карты
    function luhnCheck(cardNumber) {
        let sum = 0;
        let alternate = false;
        
        for (let i = cardNumber.length - 1; i >= 0; i--) {
            let n = parseInt(cardNumber.charAt(i), 10);
            
            if (alternate) {
                n *= 2;
                if (n > 9) {
                    n = (n % 10) + 1;
                }
            }
            
            sum += n;
            alternate = !alternate;
        }
        
        return (sum % 10) === 0;
    }
    
    // Определение типа карты
    function getCardType(cardNumber) {
        const patterns = {
            'Visa': /^4[0-9]{15}$/,
            'MasterCard': /^5[1-5][0-9]{14}$/,
            'Humo': /^9860[0-9]{12}$/,
            'Uzcard': /^8600[0-9]{12}$/
        };
        
        for (const [type, pattern] of Object.entries(patterns)) {
            if (pattern.test(cardNumber)) {
                return type;
            }
        }
        
        return null;
    }
    
    function showValidationError(input, message) {
        input.classList.add('error');
        input.classList.remove('success');
        
        let errorElement = input.parentNode.querySelector('.validation-error');
        if (!errorElement) {
            errorElement = document.createElement('div');
            errorElement.className = 'validation-error';
            input.parentNode.appendChild(errorElement);
        }
        errorElement.textContent = message;
    }
    
    function showValidationSuccess(input, message = '') {
        input.classList.add('success');
        input.classList.remove('error');
        
        clearValidationError(input);
        
        if (message) {
            let successElement = input.parentNode.querySelector('.validation-success');
            if (!successElement) {
                successElement = document.createElement('div');
                successElement.className = 'validation-success';
                input.parentNode.appendChild(successElement);
            }
            successElement.textContent = message;
        }
    }
    
    function clearValidationError(input) {
        input.classList.remove('error');
        const errorElement = input.parentNode.querySelector('.validation-error');
        if (errorElement) {
            errorElement.remove();
        }
        const successElement = input.parentNode.querySelector('.validation-success');
        if (successElement) {
            successElement.remove();
        }
    }
});
