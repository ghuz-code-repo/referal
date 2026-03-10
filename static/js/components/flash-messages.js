/**
 * Показать flash сообщение
 */
function showFlashMessage(type, message) {
    // Создаем контейнер для flash сообщений, если его нет
    let flashContainer = document.querySelector('.flash-messages');
    if (!flashContainer) {
        flashContainer = document.createElement('div');
        flashContainer.className = 'flash-messages';
        document.body.appendChild(flashContainer);
    }
    
    // Создаем flash сообщение
    const flashDiv = document.createElement('div');
    flashDiv.className = `flash-message flash-${type}`;
    flashDiv.innerHTML = `
        <span class="flash-icon">
            ${type === 'success' ? '<i class="fas fa-check-circle"></i>' : '<i class="fas fa-exclamation-circle"></i>'}
        </span>
        <span class="flash-text">${message}</span>
        <button class="flash-close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    // Добавляем сообщение
    flashContainer.appendChild(flashDiv);
    
    // Автоматически скрываем через 5 секунд
    setTimeout(function() {
        flashDiv.style.opacity = '0';
        setTimeout(function() {
            flashDiv.remove();
        }, 300);
    }, 5000);
}

/**
 * Обработка flash сообщений (серверных и динамических)
 */
function hideFlashMessage() {
    // Auto-dismiss all server-rendered flash messages after 8 seconds
    var flashMessages = document.querySelectorAll('.flash-messages .flash-message');
    flashMessages.forEach(function(msg) {
        setTimeout(function() {
            msg.style.opacity = '0';
            setTimeout(function() {
                msg.remove();
            }, 300);
        }, 8000);
    });
}

/**
 * Инициализация flash сообщений
 */
function initFlashMessages() {
    hideFlashMessage();
}
