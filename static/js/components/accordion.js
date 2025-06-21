document.addEventListener('DOMContentLoaded', function() {
    const toggles = document.querySelectorAll('.section-toggle');
    
    toggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            const targetId = this.dataset.target;
            const content = document.getElementById(targetId);
            const isActive = this.classList.contains('active');
            
            if (isActive) {
                closeSection(this, content);
            } else {
                switchToSection(this, content);
            }
        });
    });
    
    function switchToSection(newToggle, newContent) {
        const currentActiveToggle = document.querySelector('.section-toggle.active');
        const currentActiveContent = currentActiveToggle ? 
            document.getElementById(currentActiveToggle.dataset.target) : null;
        
        // Если есть активная секция, плавно скрываем её
        if (currentActiveContent && currentActiveToggle !== newToggle) {
            currentActiveToggle.classList.remove('active');
            currentActiveContent.classList.remove('show');
        }
        
        // Показываем новую секцию
        newToggle.classList.add('active');
        newContent.style.display = 'block';
        
        // Принудительно запускаем reflow
        requestAnimationFrame(() => {
            newContent.offsetHeight;
            newContent.classList.add('show');
        });
        
        // Скрываем старую секцию после завершения анимации
        if (currentActiveContent) {
            setTimeout(() => {
                if (!currentActiveContent.classList.contains('show')) {
                    currentActiveContent.style.display = 'none';
                }
            }, 650);
        }
    }
    
    function closeSection(toggle, content) {
        toggle.classList.remove('active');
        content.classList.remove('show');
        
        setTimeout(() => {
            if (!content.classList.contains('show')) {
                content.style.display = 'none';
            }
        }, 650);
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
                        toggle.click();
                    }
                }
            }
        });
    }
    
    const form = document.querySelector('.user-form');
    if (form) {
        form.addEventListener('submit', function() {
            setTimeout(openSectionWithErrors, 100);
        });
    }
});
