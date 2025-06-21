/**
 * Обработчик модального окна информации о пользователе
 */
document.addEventListener('DOMContentLoaded', function() {
    // Обработчики для открытия модальных окон пользователей
    const userLinks = document.querySelectorAll('.user-login-link');
    
    userLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const userId = this.getAttribute('data-user-id');
            
            if (userId) {
                const modal = document.getElementById(`UserInfoModal_${userId}`);
                if (modal) {
                    modal.style.display = 'block';
                    console.log('Открываю модальное окно:', `UserInfoModal_${userId}`);
                } else {
                    console.log('Не найдено модальное окно:', `UserInfoModal_${userId}`);
                }
            } else {
                console.log('Не найден user-id');
            }
        });
    });
    
    // Обработчики для закрытия модальных окон пользователей
    const userModals = document.querySelectorAll('[id^="UserInfoModal_"]');
    
    userModals.forEach(modal => {
        const closeBtn = modal.querySelector('.close');
        
        // Закрытие по клику на крестик
        if (closeBtn) {
            closeBtn.addEventListener('click', function() {
                modal.style.display = 'none';
            });
        }
        
        // Закрытие по клику вне модального окна
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });
    });
    
    // Закрытие по нажатию Escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            userModals.forEach(modal => {
                if (modal.style.display === 'block') {
                    modal.style.display = 'none';
                }
            });
        }
    });
});
