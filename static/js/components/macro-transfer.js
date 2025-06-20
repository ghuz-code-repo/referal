/**
 * Обработка переноса данных из MacroCRM в карточку реферала
 */
function initMacroTransfer() {
    console.log('Initializing macro transfer functionality...');
    
    // Обработка кликов по кнопкам переноса
    document.addEventListener('click', function(e) {
        if (e.target.closest('.transfer-macro-btn')) {
            e.preventDefault();
            const button = e.target.closest('.transfer-macro-btn');
            
            if (button.classList.contains('disabled')) {
                console.log('Transfer button is disabled');
                return;
            }
            
            const sourceField = button.getAttribute('data-source-field');
            const targetField = button.getAttribute('data-target-field');
            const referalId = button.getAttribute('data-referal-id');
            
            console.log('Transfer data:', { sourceField, targetField, referalId });
            
            transferFieldData(sourceField, targetField, referalId);
        }
        
        // Перенос всех данных
        if (e.target.closest('.transfer-all-btn')) {
            e.preventDefault();
            const button = e.target.closest('.transfer-all-btn');
            const referalId = button.getAttribute('data-referal-id');
            
            console.log('Transfer all data for referal:', referalId);
            transferAllData(referalId);
        }
    });
    
    // Обработка изменений в выпадающих списках телефонов
    document.addEventListener('change', function(e) {
        if (e.target.matches('select[data-field="macro_phone"]')) {
            // Убираем фокус с выпадающего списка после выбора
            e.target.blur();
            updateTransferButtonsState();
        }
    });
    
    // Дополнительно обрабатываем клик по опции (для некоторых браузеров)
    document.addEventListener('click', function(e) {
        if (e.target.matches('select[data-field="macro_phone"] option')) {
            // Убираем фокус с родительского select после выбора опции
            setTimeout(() => {
                e.target.parentElement.blur();
            }, 10);
        }
    });
    
    // Обновляем состояние кнопок при изменении полей
    updateTransferButtonsState();
    updateTransferAllButtonState();
    
    // Наблюдаем за изменениями в полях MacroCRM
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'attributes' && mutation.attributeName === 'value') {
                updateTransferButtonsState();
                updateTransferAllButtonState();
            }
        });
    });
    
    // Наблюдаем за всеми полями MacroCRM
    const macroFields = document.querySelectorAll('.macro-card .readonly-input');
    macroFields.forEach(field => {
        observer.observe(field, { attributes: true });
        field.addEventListener('input', function() {
            updateTransferButtonsState();
            updateTransferAllButtonState();
        });
    });
}

/**
 * Перенос данных из поля MacroCRM в поле реферала
 */
function transferFieldData(sourceField, targetField, referalId) {
    const sourceElement = document.querySelector(`[data-field="${sourceField}"][data-referal-id="${referalId}"]`);
    const targetElement = document.querySelector(`[data-field="${targetField}"][data-referal-id="${referalId}"]`);
    
    if (!sourceElement || !targetElement) {
        console.error('Source or target element not found:', { sourceField, targetField, referalId });
        return;
    }
    
    let sourceValue;
    
    // Специальная обработка для выпадающего списка телефонов
    if (sourceElement.tagName === 'SELECT' && sourceField === 'macro_phone') {
        sourceValue = sourceElement.value;
        if (!sourceValue || sourceValue.trim() === '') {
            alert('Телефон не выбран в списке');
            return;
        }
    } else {
        sourceValue = sourceElement.value || sourceElement.textContent || '';
    }
    
    if (!sourceValue.trim() || sourceValue === 'Недоступно') {
        console.log('Source field is empty or unavailable, nothing to transfer');
        return;
    }
    
    // Специальная обработка для даты
    if (sourceField === 'macro_passport_date' && targetField === 'referal_passport_date') {
        // Конвертируем дату из формата ДД.ММ.ГГГГ в ГГГГ-ММ-ДД для input[type="date"]
        const dateMatch = sourceValue.match(/(\d{2})\.(\d{2})\.(\d{4})/);
        if (dateMatch) {
            const [, day, month, year] = dateMatch;
            sourceValue = `${year}-${month}-${day}`;
        }
    }
    
    // Переносим значение
    if (targetElement.tagName === 'INPUT') {
        targetElement.value = sourceValue;
    } else {
        targetElement.textContent = sourceValue;
    }
    
    // Добавляем визуальную индикацию успешного переноса
    targetElement.classList.add('field-updated');
    
    // Показываем уведомление
    showFieldUpdateNotification(targetElement, 'Данные перенесены');
    
    // Убираем класс через некоторое время
    setTimeout(() => {
        targetElement.classList.remove('field-updated');
    }, 800);
    
    // Обновляем состояние кнопок
    updateTransferButtonsState();
    
    console.log('Data transferred successfully:', { from: sourceField, to: targetField, value: sourceValue });
}

/**
 * Перенос всех доступных данных из MacroCRM
 */
function transferAllData(referalId) {
    const fieldMappings = [
        { source: 'macro_full_name', target: 'referal_full_name' },
        { source: 'macro_phone', target: 'referal_phone' },
        { source: 'macro_passport_number', target: 'referal_passport_number' },
        { source: 'macro_passport_giver', target: 'referal_passport_giver' },
        { source: 'macro_passport_date', target: 'referal_passport_date' },
        { source: 'macro_passport_address', target: 'referal_passport_address' },
        { source: 'macro_agreement_number', target: 'referal_agreement_number' }
    ];
    
    let transferredCount = 0;
    
    fieldMappings.forEach(mapping => {
        const sourceElement = document.querySelector(`[data-field="${mapping.source}"][data-referal-id="${referalId}"]`);
        const targetElement = document.querySelector(`[data-field="${mapping.target}"][data-referal-id="${referalId}"]`);
        
        if (sourceElement && targetElement) {
            let sourceValue;
            
            // Специальная обработка для выпадающего списка телефонов
            if (sourceElement.tagName === 'SELECT' && mapping.source === 'macro_phone') {
                sourceValue = sourceElement.value;
            } else {
                sourceValue = sourceElement.value || sourceElement.textContent || '';
            }
            
            if (sourceValue.trim() && sourceValue !== 'Недоступно') {
                // Специальная обработка для даты
                if (mapping.source === 'macro_passport_date' && mapping.target === 'referal_passport_date') {
                    const dateMatch = sourceValue.match(/(\d{2})\.(\d{2})\.(\d{4})/);
                    if (dateMatch) {
                        const [, day, month, year] = dateMatch;
                        sourceValue = `${year}-${month}-${day}`;
                    }
                }
                
                if (targetElement.tagName === 'INPUT') {
                    targetElement.value = sourceValue;
                } else {
                    targetElement.textContent = sourceValue;
                }
                
                targetElement.classList.add('field-updated');
                setTimeout(() => {
                    targetElement.classList.remove('field-updated');
                }, 800);
                
                transferredCount++;
            }
        }
    });
    
    if (transferredCount > 0) {
        // Показываем общее уведомление
        const macroCard = document.querySelector(`.macro-card[data-referal-id="${referalId}"]`);
        if (macroCard) {
            showFieldUpdateNotification(macroCard, `Перенесено ${transferredCount} полей`);
        }
        console.log(`Transferred ${transferredCount} fields for referal ${referalId}`);
    } else {
        console.log('No data available to transfer');
        alert('Нет доступных данных для переноса или не выбран телефон');
    }
}

/**
 * Обновление состояния кнопок переноса (активные/неактивные)
 */
function updateTransferButtonsState() {
    const transferButtons = document.querySelectorAll('.transfer-macro-btn');
    
    transferButtons.forEach(button => {
        const sourceField = button.getAttribute('data-source-field');
        const referalId = button.getAttribute('data-referal-id');
        const sourceElement = document.querySelector(`[data-field="${sourceField}"][data-referal-id="${referalId}"]`);
        
        if (sourceElement) {
            let sourceValue;
            
            // Специальная обработка для выпадающего списка
            if (sourceElement.tagName === 'SELECT') {
                sourceValue = sourceElement.value;
            } else {
                sourceValue = sourceElement.value || sourceElement.textContent || '';
            }
            
            // Для селекта телефонов кнопка всегда активна, если есть хотя бы одна опция
            if (sourceElement.tagName === 'SELECT' && sourceField === 'macro_phone') {
                const hasOptions = sourceElement.options.length > 0;
                if (hasOptions) {
                    button.classList.remove('disabled');
                    button.disabled = false;
                } else {
                    button.classList.add('disabled');
                    button.disabled = true;
                }
            } else if (sourceValue && sourceValue.trim() && sourceValue !== 'Недоступно') {
                button.classList.remove('disabled');
                button.disabled = false;
            } else {
                button.classList.add('disabled');
                button.disabled = true;
            }
        }
    });
}

/**
 * Обновление состояния кнопки "Перенести все данные"
 */
function updateTransferAllButtonState() {
    const transferAllButtons = document.querySelectorAll('.transfer-all-btn');
    
    transferAllButtons.forEach(button => {
        const referalId = button.getAttribute('data-referal-id');
        
        // Проверяем все поля MacroCRM для данного реферала
        const macroFields = document.querySelectorAll(`[data-field^="macro_"][data-referal-id="${referalId}"]`);
        let hasData = false;
        
        macroFields.forEach(field => {
            const value = field.value || field.textContent || '';
            if (value.trim() && value !== 'Недоступно') {
                hasData = true;
            }
        });
        
        if (hasData) {
            button.classList.remove('disabled');
            button.disabled = false;
        } else {
            button.classList.add('disabled');
            button.disabled = true;
        }
    });
}

/**
 * Показать уведомление об обновлении поля
 */
function showFieldUpdateNotification(element, message) {
    // Удаляем существующее уведомление если есть
    const existingNotification = element.parentElement.querySelector('.field-update-notification');
    if (existingNotification) {
        existingNotification.remove();
    }
    
    // Создаем новое уведомление
    const notification = document.createElement('div');
    notification.className = 'field-update-notification';
    notification.textContent = message;
    
    // Позиционируем относительно поля
    element.parentElement.style.position = 'relative';
    element.parentElement.appendChild(notification);
    
    // Удаляем уведомление через 2 секунды
    setTimeout(() => {
        notification.remove();
    }, 2000);
}