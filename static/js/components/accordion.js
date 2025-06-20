document.addEventListener('DOMContentLoaded', function() {
    // Инициализация аккордеона
    const toggles = document.querySelectorAll('.section-toggle');
    
    toggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            const targetId = this.dataset.target;
            const content = document.getElementById(targetId);
            const isActive = this.classList.contains('active');
            
            if (isActive) {
                // Закрываем текущую секцию
                closeSection(this, content);
            } else {
                // Сначала закрываем все остальные секции
                closeAllSections();
                
                // Затем открываем выбранную секцию с небольшой задержкой
                setTimeout(() => {
                    openSection(this, content);
                }, 100);
            }
        });
    });
    
    function openSection(toggle, content) {
        toggle.classList.add('active');
        content.style.display = 'block';
        
        // Принудительно запускаем reflow для анимации
        content.offsetHeight;
        
        content.classList.add('show');
    }
    
    function closeSection(toggle, content) {
        toggle.classList.remove('active');
        content.classList.remove('show');
        
        // Ждем завершения анимации перед скрытием
        setTimeout(() => {
            if (!content.classList.contains('show')) {
                content.style.display = 'none';
            }
        }, 400); // Время должно совпадать с transition в CSS
    }
    
    function closeAllSections() {
        toggles.forEach(toggle => {
            const targetId = toggle.dataset.target;
            const content = document.getElementById(targetId);
            if (toggle.classList.contains('active')) {
                closeSection(toggle, content);
            }
        });
    }
    
    // Функция для открытия секции с ошибками валидации
    function openSectionWithErrors() {
        const inputs = document.querySelectorAll('.form-input');
        inputs.forEach(input => {
            if (input.classList.contains('error') || input.validity && !input.validity.valid) {
                const section = input.closest('.section-content');
                if (section) {
                    const sectionId = section.id;
                    const toggle = document.querySelector(`[data-target="${sectionId}"]`);
                    if (toggle && !toggle.classList.contains('active')) {
                        // Закрываем все секции и открываем нужную
                        closeAllSections();
                        setTimeout(() => {
                            openSection(toggle, section);
                        }, 200);
                    }
                }
            }
        });
    }
    
    // Открываем секции с ошибками после отправки формы
    const form = document.querySelector('.user-form');
    if (form) {
        form.addEventListener('submit', function() {
            setTimeout(openSectionWithErrors, 100);
        });
    }
});
