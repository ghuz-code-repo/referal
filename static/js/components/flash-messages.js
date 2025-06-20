/**
 * Обработка flash сообщений
 */
function hideFlashMessage() {
    var flashMessage = document.getElementById('flash-message');
    if (flashMessage) {
        setTimeout(function() {
            flashMessage.style.display = 'none';
        }, 3000);
    }
}

/**
 * Инициализация flash сообщений
 */
function initFlashMessages() {
    hideFlashMessage();
}
