/**
 * Обработка модальных окон
 */
function initModalHandler() {
    console.log('Initializing modal handler...');
    
    // Обработка открытия модальных окон
    document.addEventListener('click', function(e) {
        console.log('Click detected on:', e.target);
        
        // Обработка кнопки "Форма скачивания договора"
        if (e.target.id === 'open_agreement') {
            e.preventDefault();
            console.log('Agreement button clicked');
            openModal('AgreementDownloadModal');
            return;
        }
        
        // Обработка кнопок "Заполнить данные"
        if (e.target.classList.contains('open_document_form')) {
            e.preventDefault();
            const referalId = e.target.getAttribute('data-referal-id');
            const modalId = `DocumentFormModal_${referalId}`;
            console.log('Document form button clicked, referal ID:', referalId);
            openModal(modalId);
            return;
        }
        
        // Обработка кнопок "Скачать акт"
        if (e.target.id === 'open_act' || e.target.closest('#open_act')) {
            e.preventDefault();
            console.log('Act download button clicked');
            openModal('ActDownloadModal');
            return;
        }
        
        // Универсальная обработка для других кнопок с паттерном open_*
        const openButton = e.target.closest('[id*="open_"]') || 
                          e.target.closest('[data-modal]');
        
        if (openButton && openButton.id && openButton.id.startsWith('open_')) {
            e.preventDefault();
            const modalId = openButton.id.replace('open_', '') + '_modal';
            console.log('Generic open button clicked:', openButton.id, 'Modal:', modalId);
            openModal(modalId);
            return;
        }

        // Обработка закрытия модальных окон
        if (e.target.classList.contains('close')) {
            e.preventDefault();
            const modal = e.target.closest('.modal');
            console.log('Close button clicked, closing modal:', modal);
            closeModal(modal);
            return;
        }

        // Закрытие при клике на фон модального окна
        if (e.target.classList.contains('modal')) {
            e.preventDefault();
            console.log('Background clicked, closing modal:', e.target);
            closeModal(e.target);
            return;
        }
    });

    // Закрытие модального окна по ESC
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const openModals = document.querySelectorAll('.modal[style*="block"]');
            openModals.forEach(modal => {
                console.log('ESC pressed, closing modal:', modal);
                closeModal(modal);
            });
        }
    });
    
    // Отладочная информация
    const agreementBtn = document.getElementById('open_agreement');
    const agreementModal = document.getElementById('AgreementDownloadModal');
    
    console.log('Agreement button:', agreementBtn);
    console.log('Agreement modal:', agreementModal);
    
    // Проверим все модальные окна на странице
    const allModals = document.querySelectorAll('.modal');
    console.log('Found modals:', allModals);
    
    // Проверим все кнопки открытия документов
    const documentButtons = document.querySelectorAll('.open_document_form');
    console.log('Found document form buttons:', documentButtons);
}

function openModal(modalId) {
    console.log('Attempting to open modal:', modalId);
    const modal = document.getElementById(modalId);
    if (modal) {
        console.log('Modal found, opening:', modal);
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
        
        // Добавляем класс для CSS анимации если нужно
        modal.classList.add('modal-open');
    } else {
        console.error('Modal not found:', modalId);
        // Выводим список всех доступных модальных окон для отладки
        const allModals = document.querySelectorAll('.modal');
        console.log('Available modals:', Array.from(allModals).map(m => m.id));
    }
}

function closeModal(modal) {
    if (modal) {
        console.log('Closing modal:', modal);
        modal.style.display = 'none';
        // document.body.style.overflow = 'auto';
        modal.classList.remove('modal-open');
    }
}

/**
 * Инициализация обработчиков модальных окон
 */
function initModalHandlers() {
    console.log('Initializing modal handlers...');
    
    // Обработка открытия модальных окон
    document.addEventListener('click', function(e) {
        if (e.target.matches('.open_document_form') || e.target.closest('.open_document_form')) {
            e.preventDefault();
            const button = e.target.matches('.open_document_form') ? e.target : e.target.closest('.open_document_form');
            const referalId = button.getAttribute('data-referal-id');
            
            console.log('Opening document form for referal:', referalId);
            
            const modal = document.getElementById(`DocumentFormModal_${referalId}`);
            if (modal) {
                modal.style.display = 'block';
                modal.classList.add('show');
                document.body.style.overflow = 'hidden';
                
                // Инициализация для нового реферала
                if (referalId === 'new') {
                    initNewReferalValidation();
                }
            } else {
                console.error('Modal not found for referal:', referalId);
            }
        }
    });
    
    // Обработка закрытия модальных окон
    document.addEventListener('click', function(e) {
        // Закрытие по кнопке X
        if (e.target.matches('.close') || e.target.closest('.close')) {
            e.preventDefault();
            const modal = e.target.closest('.modal');
            if (modal) {
                closeModal(modal);
            }
        }
        
        // Закрытие по клику вне модального окна
        if (e.target.matches('.modal')) {
            closeModal(e.target);
        }
    });
    
    // Закрытие по ESC
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const openModal = document.querySelector('.modal.show');
            if (openModal) {
                closeModal(openModal);
            }
        }
    });
}

/**
 * Инициализация валидации для нового реферала
 */
function initNewReferalValidation() {
    console.log('Initializing validation for new referal...');
    
    const modal = document.getElementById('DocumentFormModal_new');
    if (!modal) return;
    
    const phoneInput = modal.querySelector('input[name="phone_number"]');
    const nameInput = modal.querySelector('input[name="full_name"]');
    
    if (phoneInput && typeof validatePhoneInput === 'function') {
        phoneInput.addEventListener('input', function(e) {
            validatePhoneInput(e.target);
        });
    }
    
    if (nameInput) {
        nameInput.addEventListener('input', function(e) {
            const value = e.target.value.trim();
            if (value.length >= 2) {
                e.target.classList.remove('error');
                e.target.classList.add('success');
                setTimeout(() => e.target.classList.remove('success'), 1000);
            } else if (value.length > 0) {
                e.target.classList.add('error');
            }
        });
    }
}
