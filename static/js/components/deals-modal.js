/**
 * Модальное окно для управления договорами реферала
 */

// Функция для получения базового пути API
function getApiBasePath() {
    // Проверяем глобальную переменную
    if (window.API_BASE_PATH) {
        return window.API_BASE_PATH;
    }
    
    // Определяем из текущего URL
    const currentPath = window.location.pathname;
    const basePath = currentPath.startsWith('/referal') ? '/referal' : '';
    console.log('🔧 API Base Path определен из URL:', basePath);
    return basePath;
}

// Глобальная переменная для хранения текущего referal_id
let currentReferalId = null;

/**
 * Открывает модальное окно с договорами реферала
 */
function openDealsModal(referalId) {
    currentReferalId = referalId;
    const modal = document.getElementById('dealsListModal');
    
    if (!modal) {
        console.error('❌ Модальное окно dealsListModal не найдено в DOM!');
        return;
    }
    
    console.log('✅ Модальное окно найдено:', modal);
    console.log('📝 HTML модалки (первые 500 символов):', modal.innerHTML.substring(0, 500));
    
    // Показываем модальное окно
    modal.style.display = 'flex';
    
    // Загружаем данные о договорах
    loadDealsData(referalId);
}

/**
 * Закрывает модальное окно
 */
function closeDealsModal() {
    const modal = document.getElementById('dealsListModal');
    if (modal) {
        modal.style.display = 'none';
    }
    currentReferalId = null;
}

/**
 * Загружает данные о договорах реферала с сервера
 */
function loadDealsData(referalId) {
    // Показываем индикатор загрузки
    const tbody = document.getElementById('deals-table-body');
    tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 40px;"><i class="fas fa-spinner fa-spin fa-2x"></i><br>Загрузка...</td></tr>';
    
    // Получаем базовый путь
    const basePath = getApiBasePath();
    const apiUrl = `${basePath}/get_referal_deals/${referalId}`;
    
    console.log('🌐 Загрузка данных о договорах, URL:', apiUrl);
    
    // Запрос к API
    fetch(apiUrl)
        .then(response => {
            console.log('📥 Ответ получен, статус:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('✅ Данные получены:', data);
            if (data.success) {
                displayDealsData(data);
            } else {
                showError(data.message || 'Ошибка загрузки данных');
            }
        })
        .catch(error => {
            console.error('❌ Ошибка:', error);
            showError('Ошибка соединения с сервером: ' + error.message);
        });
}

/**
 * Отображает данные о договорах в таблице
 */
function displayDealsData(data) {
    console.log('📊 displayDealsData called with:', data);
    
    // Список всех необходимых элементов
    const elementIds = [
        'deals-referal-name-header',
        'referal-full-name', 
        'referal-phone',
        'referal-contact-id',
        'referal-passport-number',
        'referal-passport-giver',
        'referal-passport-date',
        'save-referal-data-btn',
        'total-deals-count',
        'total-withdrawal-amount',
        'deals-table-body'
    ];
    
    // Проверяем наличие всех элементов
    const missingElements = [];
    elementIds.forEach(id => {
        const element = document.getElementById(id);
        if (!element) {
            missingElements.push(id);
            console.error(`❌ Элемент не найден: ${id}`);
        } else {
            console.log(`✅ Элемент найден: ${id}`);
        }
    });
    
    if (missingElements.length > 0) {
        const errorMsg = `Не найдены элементы: ${missingElements.join(', ')}`;
        console.error('❌ ' + errorMsg);
        showError(errorMsg);
        return;
    }
    
    // Обновляем заголовок с именем реферала
    document.getElementById('deals-referal-name-header').textContent = data.referal_name || 'Неизвестно';
    
    // Заполняем информацию о реферале (теперь это input поля)
    document.getElementById('referal-full-name').value = data.referal_name || '';
    document.getElementById('referal-phone').value = data.referal_phone || '';
    document.getElementById('referal-contact-id').value = data.referal_contact_id || '';
    
    // Заполняем паспортные данные (если есть)
    document.getElementById('referal-passport-number').value = data.passport_number || '';
    document.getElementById('referal-passport-giver').value = data.passport_giver || '';
    document.getElementById('referal-passport-date').value = data.passport_date || '';
    
    // Сохраняем referal_id для последующего сохранения
    const saveBtn = document.getElementById('save-referal-data-btn');
    saveBtn.dataset.referalId = currentReferalId;
    
    // Обновляем сводку
    document.getElementById('total-deals-count').textContent = data.total_deals || 0;
    document.getElementById('total-withdrawal-amount').textContent = (data.total_withdrawal || 0).toLocaleString('ru-RU');
    
    // Обновляем таблицу
    const tbody = document.getElementById('deals-table-body');
    
    if (!data.deals || data.deals.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="4" style="text-align: center; padding: 40px;">
                    <i class="fas fa-inbox fa-2x"></i><br>
                    <p style="margin-top: 16px;">Договоры не найдены</p>
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = '';
    data.deals.forEach((deal, index) => {
        const row = createDealRow(deal, index);
        tbody.appendChild(row);
    });
}

/**
 * Создает строку таблицы для договора
 */
function createDealRow(deal, index) {
    const tr = document.createElement('tr');
    const basePath = getApiBasePath();
    
    console.log('📊 Creating row for deal:', deal);
    
    // Определяем, можно ли отправить на проверку
    // Кнопка показывается только для статуса 0 (Заполнить данные) или если статус не определён
    const statusId = deal.status_id ?? 0; // Если null/undefined, считаем что 0
    const canSendForReview = statusId === 0;
    
    tr.innerHTML = `
        <td>${index + 1}</td>
        <td><strong>${deal.agreement_number || '—'}</strong></td>
        <td>${(deal.withdrawal_amount || 0).toLocaleString('ru-RU')} ₽</td>
        <td class="deal-actions">
            <a href="${basePath}/get_deal_act/${deal.referal_deal_id}" 
               class="btn-icon btn-download" 
               title="Скачать акт"
               target="_blank">
                <i class="fas fa-download"></i> Скачать акт
            </a>
            ${canSendForReview ? `
                <button class="btn-icon btn-send" 
                        onclick="sendDealForReview(${deal.referal_deal_id})"
                        title="Отправить на проверку">
                    <i class="fas fa-paper-plane"></i> На проверку
                </button>
            ` : `
                <span class="deal-status-badge status-${statusId}">
                    ${deal.status_name || 'Статус неизвестен'}
                </span>
            `}
        </td>
    `;
    
    return tr;
}



/**
 * Отправляет договор на проверку
 */
function sendDealForReview(referalDealId) {
    if (!confirm('Вы уверены, что хотите отправить этот договор на проверку?')) {
        return;
    }
    
    // Показываем индикатор загрузки
    const button = event.target.closest('button');
    const originalHtml = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Отправка...';
    
    // Получаем базовый путь
    const basePath = getApiBasePath();
    
    // Отправляем запрос на тот же endpoint что и на вкладке "Документы"
    fetch(`${basePath}/deal/${referalDealId}/send_for_review`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Показываем успешное сообщение
            showFlashMessage('success', data.message || 'Договор отправлен на проверку');
            
            // Меняем кнопку на индикатор успеха
            button.innerHTML = '<i class="fas fa-check"></i> Отправлено';
            button.classList.add('btn-success');
            button.classList.remove('btn-primary');
            
            // Через 1 секунду перезагружаем данные (кнопка исчезнет)
            setTimeout(() => {
                loadDealsData(currentReferalId);
            }, 1000);
        } else {
            showFlashMessage('error', data.message || 'Ошибка при отправке договора');
            button.disabled = false;
            button.innerHTML = originalHtml;
        }
    })
    .catch(error => {
        console.error('Ошибка:', error);
        showFlashMessage('error', 'Ошибка соединения с сервером');
        button.disabled = false;
        button.innerHTML = originalHtml;
    });
}

/**
 * Показывает сообщение об ошибке в таблице
 */
function showError(message) {
    const tbody = document.getElementById('deals-table-body');
    tbody.innerHTML = `
        <tr>
            <td colspan="8" style="text-align: center; padding: 40px; color: #dc3545;">
                <i class="fas fa-exclamation-triangle fa-2x"></i>
                <p>${message}</p>
            </td>
        </tr>
    `;
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Обработчики для кнопок "Меню реферала"
    document.querySelectorAll('.open-deals-modal-btn').forEach(button => {
        button.addEventListener('click', function() {
            const referalId = this.getAttribute('data-referal-id');
            console.log('🔘 Opening deals modal for referal:', referalId);
            openDealsModal(referalId);
        });
    });
    
    // Обработчики для кнопок "Просмотреть договоры" (старые, для совместимости)
    document.querySelectorAll('.view-deals-btn').forEach(button => {
        button.addEventListener('click', function() {
            const referalId = this.getAttribute('data-referal-id');
            openDealsModal(referalId);
        });
    });
    
    // Обработчики для кнопок "Управление договорами" (старые, для совместимости)
    document.querySelectorAll('.manage-deals-btn').forEach(button => {
        button.addEventListener('click', function() {
            const referalId = this.getAttribute('data-referal-id');
            openDealsModal(referalId);
        });
    });
    
    // Обработчик кнопки сохранения данных реферала
    const saveReferalBtn = document.getElementById('save-referal-data-btn');
    if (saveReferalBtn) {
        saveReferalBtn.addEventListener('click', function() {
            saveReferalData();
        });
    }
    
    // Закрытие по клику вне модального окна
    const modal = document.getElementById('dealsListModal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeDealsModal();
            }
        });
    }
    
    // Закрытие по ESC
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeDealsModal();
        }
    });
});

/**
 * Сохраняет паспортные данные реферала
 */
function saveReferalData() {
    const referalId = currentReferalId;
    
    if (!referalId) {
        showFlashMessage('error', 'Ошибка: ID реферала не определен');
        return;
    }
    
    // Собираем все данные реферала
    const fullName = document.getElementById('referal-full-name').value;
    const phone = document.getElementById('referal-phone').value;
    const contactId = document.getElementById('referal-contact-id').value;
    const passportNumber = document.getElementById('referal-passport-number').value;
    const passportGiver = document.getElementById('referal-passport-giver').value;
    const passportDate = document.getElementById('referal-passport-date').value;
    
    const saveBtn = document.getElementById('save-referal-data-btn');
    const originalText = saveBtn.innerHTML;
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Сохранение...';
    
    const basePath = getApiBasePath();
    
    fetch(`${basePath}/update_referal_documents/${referalId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
            'full_name': fullName,
            'phone': phone,
            'contact_id': contactId,
            'passport_number': passportNumber,
            'passport_giver': passportGiver,
            'passport_date': passportDate
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showFlashMessage('success', 'Данные реферала успешно сохранены');
        } else {
            showFlashMessage('error', data.message || 'Ошибка при сохранении данных');
        }
    })
    .catch(error => {
        console.error('Ошибка:', error);
        showFlashMessage('error', 'Ошибка соединения с сервером');
    })
    .finally(() => {
        saveBtn.disabled = false;
        saveBtn.innerHTML = originalText;
    });
}

/**
 * Показывает flash-сообщение
 */
function showFlashMessage(type, message) {
    // Просто создаём уведомление
    const isSuccess = type === 'success';
    const bgColor = isSuccess ? '#d4edda' : '#f8d7da';
    const textColor = isSuccess ? '#155724' : '#721c24';
    const borderColor = isSuccess ? '#c3e6cb' : '#f5c6cb';
    
    const alertDiv = document.createElement('div');
    alertDiv.style.cssText = `
        position: fixed; 
        top: 20px; 
        right: 20px; 
        z-index: 9999; 
        padding: 15px 20px; 
        border-radius: 6px; 
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        background-color: ${bgColor};
        color: ${textColor};
        border: 1px solid ${borderColor};
    `;
    alertDiv.textContent = message;
    
    document.body.appendChild(alertDiv);
    
    setTimeout(() => {
        alertDiv.style.opacity = '0';
        alertDiv.style.transition = 'opacity 0.3s';
        setTimeout(() => alertDiv.remove(), 300);
    }, 3000);
}

/**
 * Показывает ошибку в таблице
 */
function showError(message) {
    const tbody = document.getElementById('deals-table-body');
    tbody.innerHTML = `
        <tr>
            <td colspan="4" style="text-align: center; padding: 40px; color: #d32f2f;">
                <i class="fas fa-exclamation-circle fa-2x"></i><br>
                <p style="margin-top: 16px;">${message}</p>
            </td>
        </tr>
    `;
}

/**
 * Открывает модал добавления договора из меню реферала
 */
function openAddDealModalFromMenu() {
    if (!currentReferalId) {
        console.error('❌ currentReferalId не определён');
        return;
    }
    
    // Получаем имя реферала из заголовка
    const referalNameElement = document.getElementById('deals-referal-name-header');
    const referalName = referalNameElement ? referalNameElement.textContent : 'Неизвестно';
    
    console.log('🔧 Открываем добавление договора для реферала:', currentReferalId, referalName);
    
    // Закрываем меню реферала
    closeDealsModal();
    
    // Открываем модал добавления договора
    openAddDealModal(currentReferalId, referalName);
}
