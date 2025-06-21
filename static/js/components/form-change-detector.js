document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('.user-form');
    const submitButton = document.querySelector('.form-actions button[type="submit"]');
    
    if (!form || !submitButton) return;
    
    const formInputs = form.querySelectorAll('input[type="text"], input[type="email"], input[type="tel"], input[type="date"]');
    let originalValues = {};
    
    // Сохраняем исходные значения полей
    function saveOriginalValues() {
        formInputs.forEach(input => {
            originalValues[input.name] = input.value;
        });
    }
    
    // Проверяем, изменились ли данные
    function checkForChanges() {
        let hasChanges = false;
        
        formInputs.forEach(input => {
            if (originalValues[input.name] !== input.value) {
                hasChanges = true;
            }
        });
        
        // Обновляем состояние кнопки
        if (hasChanges) {
            enableSubmitButton();
        } else {
            disableSubmitButton();
        }
    }
    
    function enableSubmitButton() {
        submitButton.disabled = false;
        submitButton.classList.remove('disabled');
        submitButton.querySelector('i').className = 'fas fa-save';
    }
    
    function disableSubmitButton() {
        submitButton.disabled = true;
        submitButton.classList.add('disabled');
        submitButton.querySelector('i').className = 'fas fa-check';
    }
    
    // Инициализация
    saveOriginalValues();
    disableSubmitButton();
    
    // Добавляем обработчики событий на все поля
    formInputs.forEach(input => {
        input.addEventListener('input', checkForChanges);
        input.addEventListener('change', checkForChanges);
    });
    
    // После успешной отправки формы обновляем исходные значения
    form.addEventListener('submit', function() {
        // Небольшая задержка для обработки flash-сообщений
        setTimeout(() => {
            // Проверяем, была ли форма успешно отправлена (нет ошибок)
            const errorMessages = document.querySelectorAll('.flash-message.error');
            if (errorMessages.length === 0) {
                saveOriginalValues();
                disableSubmitButton();
            }
        }, 100);
    });
    
    // Обработка успешного сохранения через flash-сообщения
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList') {
                const successMessages = document.querySelectorAll('.flash-message.success');
                if (successMessages.length > 0) {
                    // Данные успешно сохранены, обновляем исходные значения
                    setTimeout(() => {
                        saveOriginalValues();
                        disableSubmitButton();
                    }, 500);
                }
            }
        });
    });
    
    // Наблюдаем за изменениями в контейнере flash-сообщений
    const flashContainer = document.querySelector('.flash-messages');
    if (flashContainer) {
        observer.observe(flashContainer, { childList: true, subtree: true });
    }
});
