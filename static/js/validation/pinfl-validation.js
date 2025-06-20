document.addEventListener('DOMContentLoaded', function() {
    const pinflInput = document.getElementById('pinfl');
    
    if (pinflInput) {
        pinflInput.addEventListener('input', function() {
            let value = this.value.replace(/\s/g, ''); // Убираем пробелы
            value = value.replace(/[^0-9]/g, ''); // Оставляем только цифры
            
            // Ограничиваем до 14 цифр
            if (value.length > 14) {
                value = value.slice(0, 14);
            }
            
            // Форматируем с пробелами (x xxxxxx xxx xxx x)
            let formattedValue = '';
            if (value.length > 0) {
                formattedValue += value.charAt(0); // Первая цифра
                
                if (value.length > 1) {
                    formattedValue += ' ' + value.substring(1, 7); // 6 цифр после пробела
                }
                
                if (value.length > 7) {
                    formattedValue += ' ' + value.substring(7, 10); // 3 цифры после пробела
                }
                
                if (value.length > 10) {
                    formattedValue += ' ' + value.substring(10, 13); // 3 цифры после пробела
                }
                
                if (value.length > 13) {
                    formattedValue += ' ' + value.charAt(13); // Последняя цифра
                }
            }
            
            this.value = formattedValue;
            validatePinfl(this);
        });
        
        pinflInput.addEventListener('blur', function() {
            validatePinfl(this);
        });
        
        // Разрешаем только цифры при вводе
        pinflInput.addEventListener('keydown', function(e) {
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
    
    function validatePinfl(input) {
        const value = input.value.replace(/\s/g, ''); // Убираем пробелы для валидации
        
        clearValidationError(input);
        
        if (value === '') {
            return true; // Поле не обязательное
        }
        
        if (value.length !== 14) {
            showValidationError(input, 'ПИНФЛ должен содержать ровно 14 цифр');
            return false;
        }
        
        // Дополнительная проверка алгоритма ПИНФЛ
        if (!validatePinflAlgorithm(value)) {
            showValidationError(input, 'Неверный ПИНФЛ');
            return false;
        }
        
        showValidationSuccess(input);
        return true;
    }
    
    function validatePinflAlgorithm(pinfl) {
        // Упрощенная проверка ПИНФЛ
        // Первые 6 цифр - дата рождения (ДДММГГ)
        const day = parseInt(pinfl.substring(0, 2));
        const month = parseInt(pinfl.substring(2, 4));
        const year = parseInt(pinfl.substring(4, 6));
        
        // if (day < 1 || day > 31) return false;
        // if (month < 1 || month > 12) return false;
        
        // // 7-я цифра - пол (нечетная - мужской, четная - женский)
        // const gender = parseInt(pinfl.substring(6, 7));
        // if (gender < 1 || gender > 9) return false;
        
        return true;
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
    
    function showValidationSuccess(input) {
        input.classList.add('success');
        input.classList.remove('error');
        clearValidationError(input);
    }
    
    function clearValidationError(input) {
        input.classList.remove('error', 'success');
        const errorElement = input.parentNode.querySelector('.validation-error');
        if (errorElement) {
            errorElement.remove();
        }
    }
});
