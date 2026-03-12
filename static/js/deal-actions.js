/**
 * Обработка действий с договорами (отправка на проверку, обновление статуса)
 */

function initDealActions() {
    console.log('Initializing deal actions...');
    
    // Обработчик кнопок "Отправить на проверку"
    document.addEventListener('click', function(e) {
        // Проверяем, что клик был по кнопке отправки
        const sendBtn = e.target.closest('.deal-send-review-btn');
        if (!sendBtn) return;
        
        e.preventDefault();
        
        const dealId = sendBtn.getAttribute('data-deal-id');
        if (!dealId) {
            console.error('Deal ID not found');
            return;
        }
        
        // Подтверждение действия
        if (!confirm('Отправить договор на проверку?')) {
            return;
        }
        
        // Блокируем кнопку
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>Отправка...</span>';
        
        // Отправляем запрос
        fetch(`/deal/${dealId}/send_for_review`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Успешно отправлено
                showNotification('success', data.message);
                
                // Обновляем UI
                updateDealStatus(dealId, data.new_status_id, data.new_status_name);
                
                // Удаляем кнопку (она больше не нужна)
                sendBtn.remove();
            } else {
                // Ошибка
                showNotification('error', data.message || 'Ошибка при отправке на проверку');
                
                // Разблокируем кнопку
                sendBtn.disabled = false;
                sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i> <span>Отправить</span>';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('error', 'Произошла ошибка при отправке запроса');
            
            // Разблокируем кнопку
            sendBtn.disabled = false;
            sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i> <span>Отправить</span>';
        });
    });
}

/**
 * Обновляет статус договора в UI
 */
function updateDealStatus(dealId, statusId, statusName) {
    const dealItem = document.querySelector(`.deal-compact-item[data-deal-id="${dealId}"]`);
    if (!dealItem) return;
    
    // Обновляем атрибут статуса
    dealItem.setAttribute('data-status-id', statusId);
    
    // Находим бейдж статуса
    const statusBadge = dealItem.querySelector('.deal-status-badge');
    if (statusBadge) {
        // Удаляем старые классы статуса
        statusBadge.className = 'deal-status-badge';
        
        // Добавляем новый класс
        statusBadge.classList.add(`status-${statusId}`);
        
        // Обновляем текст
        statusBadge.textContent = statusName;
        
        // Добавляем анимацию
        statusBadge.style.animation = 'pulse 0.5s ease';
        setTimeout(() => {
            statusBadge.style.animation = '';
        }, 500);
    }
}

/**
 * Показывает уведомление пользователю
 */
function showNotification(type, message) {
    // Создаем элемент уведомления
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}"></i>
            <span>${message}</span>
        </div>
    `;
    
    // Добавляем в body
    document.body.appendChild(notification);
    
    // Показываем с анимацией
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    // Автоматически скрываем через 3 секунды
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 3000);
}

// CSS стили для уведомлений (добавляются динамически)
function addNotificationStyles() {
    if (document.getElementById('deal-notification-styles')) return;
    
    const style = document.createElement('style');
    style.id = 'deal-notification-styles';
    style.textContent = `
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 16px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            z-index: 10000;
            opacity: 0;
            transform: translateX(400px);
            transition: all 0.3s ease;
        }
        
        .notification.show {
            opacity: 1;
            transform: translateX(0);
        }
        
        .notification-success {
            background: #d1e7dd;
            border-left: 4px solid #0f5132;
            color: #0f5132;
        }
        
        .dark-theme .notification-success {
            background: #0a3622;
            color: #a3cfbb;
        }
        
        .notification-error {
            background: #f8d7da;
            border-left: 4px solid #721c24;
            color: #721c24;
        }
        
        .dark-theme .notification-error {
            background: #58151c;
            color: #f5c2c7;
        }
        
        .notification-content {
            display: flex;
            align-items: center;
            gap: 12px;
            font-weight: 500;
        }
        
        .notification-content i {
            font-size: 18px;
        }
        
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
        }
    `;
    
    document.head.appendChild(style);
}

// Инициализация при загрузке DOM
document.addEventListener('DOMContentLoaded', function() {
    initDealActions();
    addNotificationStyles();
    console.log('Deal actions initialized');
});
