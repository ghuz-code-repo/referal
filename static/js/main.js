/**
 * Главный файл инициализации JavaScript компонентов
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing components...');
    
    // Инициализация валидации телефонов
    if (typeof initPhoneValidation === 'function') {
        initPhoneValidation();
        console.log('Phone validation initialized');
    }
    
    // Инициализация валидации PINFL
    if (typeof initPinflValidation === 'function') {
        initPinflValidation();
        console.log('PINFL validation initialized');
    }
    
    // Инициализация валидации email
    if (typeof initEmailValidation === 'function') {
        initEmailValidation();
        console.log('Email validation initialized');
    }
    
    // Инициализация валидации паспорта
    if (typeof initPassportValidation === 'function') {
        initPassportValidation();
        console.log('Passport validation initialized');
    }
    
    // Инициализация компонентов
    if (typeof initFlashMessages === 'function') {
        initFlashMessages();
        console.log('Flash messages initialized');
    }
    
    // Инициализация модальных окон
    if (typeof initModalHandler === 'function') {
        initModalHandler();
        console.log('Modal handler initialized');
    }
    
    // Инициализация переноса данных MacroCRM
    if (typeof initMacroTransfer === 'function') {
        initMacroTransfer();
        console.log('Macro transfer initialized');
    }
});

// Инициализация flash сообщений при загрузке страницы
window.addEventListener('load', function() {
    if (typeof hideFlashMessage === 'function') {
        hideFlashMessage();
    }
});
