document.addEventListener('DOMContentLoaded', function() {
    const transSchetInput = document.getElementById('trans_schet');
    const mfoInput = document.getElementById('mfo');
    
    // Валидация транзитного счета
    if (transSchetInput) {
        transSchetInput.addEventListener('input', function() {
            // Оставляем только цифры
            let value = this.value.replace(/[^0-9]/g, '');
            
            // Ограничиваем до 20 цифр (стандартная длина счета)
            if (value.length > 20) {
                value = value.slice(0, 20);
            }
            
            this.value = value;
            validateTransSchet(this);
        });
        
        transSchetInput.addEventListener('blur', function() {
            validateTransSchet(this);
        });
        
        // Разрешаем только цифры при вводе
        transSchetInput.addEventListener('keydown', function(e) {
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
    
    // Валидация МФО
    if (mfoInput) {
        mfoInput.addEventListener('input', function() {
            // Оставляем только цифры
            let value = this.value.replace(/[^0-9]/g, '');
            
            // Ограничиваем до 5 цифр (стандартная длина МФО в Узбекистане)
            if (value.length > 5) {
                value = value.slice(0, 5);
            }
            
            this.value = value;
            validateMfo(this);
        });
        
        mfoInput.addEventListener('blur', function() {
            validateMfo(this);
        });
        
        // Разрешаем только цифры при вводе
        mfoInput.addEventListener('keydown', function(e) {
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
    
    function validateTransSchet(input) {
        const value = input.value.trim();
        
        clearValidationError(input);
        
        if (value === '') {
            return true; // Поле не обязательное
        }
        
        if (value.length < 8) {
            showValidationError(input, 'Транзитный счет должен содержать минимум 8 цифр');
            return false;
        }
        
        if (value.length > 20) {
            showValidationError(input, 'Транзитный счет не должен превышать 20 цифр');
            return false;
        }
        
        showValidationSuccess(input);
        return true;
    }
    
    function validateMfo(input) {
        const value = input.value.trim();
        
        clearValidationError(input);
        
        if (value === '') {
            return true; // Поле не обязательное
        }
        
        if (value.length !== 5) {
            showValidationError(input, 'МФО должен содержать ровно 5 цифр');
            return false;
        }
        
        showValidationSuccess(input);
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
