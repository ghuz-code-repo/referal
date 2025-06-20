/**
 * Отладочный скрипт для модальных окон
 */
function debugModals() {
    console.log('=== MODAL DEBUG ===');
    
    // Проверяем все кнопки
    const buttons = document.querySelectorAll('button');
    console.log('All buttons on page:', buttons);
    
    buttons.forEach((btn, index) => {
        console.log(`Button ${index}:`, {
            id: btn.id,
            className: btn.className,
            textContent: btn.textContent,
            element: btn
        });
    });
    
    // Проверяем все модальные окна
    const modals = document.querySelectorAll('.modal');
    console.log('All modals on page:', modals);
    
    modals.forEach((modal, index) => {
        console.log(`Modal ${index}:`, {
            id: modal.id,
            className: modal.className,
            display: window.getComputedStyle(modal).display,
            element: modal
        });
    });
    
    // Проверяем конкретные элементы
    const agreementBtn = document.getElementById('open_agreement');
    const agreementModal = document.getElementById('agreement_modal');
    
    console.log('Specific elements:');
    console.log('- Agreement button:', agreementBtn);
    console.log('- Agreement modal:', agreementModal);
    
    // Тестируем открытие модального окна
    if (agreementBtn && agreementModal) {
        console.log('Adding test click listener...');
        agreementBtn.addEventListener('click', function(e) {
            console.log('TEST: Agreement button clicked');
            e.preventDefault();
            agreementModal.style.display = 'block';
            console.log('TEST: Modal should now be visible');
        });
    }
}

// Запускаем отладку после загрузки DOM
document.addEventListener('DOMContentLoaded', debugModals);
