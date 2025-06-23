/**
 * Универсальный менеджер тем для проектов Golden House
 * Обеспечивает синхронизацию темы между сервисами через localStorage и Cookie
 */

/**
 * УСТРАНЕНИЕ FOUC + СИНХРОНИЗАЦИЯ МЕЖДУ СЕРВИСАМИ
 */

// ИСПРАВЛЕНИЕ FOUC БЕЗ ИЗМЕНЕНИЯ ЦВЕТОВ - только применение класса dark-theme
(function() {
    function getCookie(name) {
        const nameEQ = name + "=";
        const ca = document.cookie.split(';');
        for(let i = 0; i < ca.length; i++) {
            let c = ca[i];
            while (c.charAt(0) === ' ') c = c.substring(1, c.length);
            if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
        }
        return null;
    }
    
    const cookieTheme = getCookie('gh_theme');
    const savedTheme = cookieTheme || localStorage.getItem('gh_theme_preference') || 'light';
    
    // ТОЛЬКО применяем класс dark-theme - НЕ МЕНЯЕМ НИКАКИХ ЦВЕТОВ
    if (savedTheme === 'dark') {
        document.documentElement.classList.add('dark-theme');
        
        // Применяем к body как только он появится
        const applyToBody = () => {
            if (document.body) {
                document.body.classList.add('dark-theme');
            } else {
                requestAnimationFrame(applyToBody);
            }
        };
        applyToBody();
        
        // MutationObserver для гарантии
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                mutation.addedNodes.forEach(function(node) {
                    if (node.nodeType === 1 && node.tagName === 'BODY') {
                        node.classList.add('dark-theme');
                    }
                });
            });
        });
        observer.observe(document.documentElement, { childList: true, subtree: true });
        
        setTimeout(() => observer.disconnect(), 1000);
    }
    
    // Синхронизация
    if (cookieTheme && cookieTheme !== localStorage.getItem('gh_theme_preference')) {
        localStorage.setItem('gh_theme_preference', cookieTheme);
    } else if (!cookieTheme && localStorage.getItem('gh_theme_preference')) {
        const expires = new Date();
        expires.setTime(expires.getTime() + (365 * 24 * 60 * 60 * 1000));
        document.cookie = `gh_theme=${localStorage.getItem('gh_theme_preference')};expires=${expires.toUTCString()};path=/;SameSite=Lax`;
    }
})();

class ThemeManager {
    constructor() {
        this.STORAGE_KEY = 'gh_theme_preference';
        this.COOKIE_KEY = 'gh_theme';
        this.DARK_THEME_CLASS = 'dark-theme';
        this.themes = {
            light: 'light',
            dark: 'dark'
        };
        
        this.logos = {
            light: null,
            dark: null
        };
        
        this.init();
    }

    init() {
        this.applyThemeImmediately();
        
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.initializeComponents());
        } else {
            this.initializeComponents();
        }

        // ИСПРАВЛЕНИЕ: Слушаем изменения в localStorage от других сервисов
        window.addEventListener('storage', (e) => {
            if (e.key === this.STORAGE_KEY && e.newValue !== e.oldValue) {
                const newTheme = e.newValue || this.themes.light;
                this.applyTheme(newTheme, false); // НЕ обновляем storage чтобы избежать циклов
                // Обновляем cookie для синхронизации с другими сервисами
                this.setCookie(this.COOKIE_KEY, newTheme, 365);
            }
        });

        // НОВОЕ: Слушаем изменения cookie через polling (для межсерверной синхронизации)
        this.startCookiePolling();
    }

    /**
     * НОВЫЙ МЕТОД: Отслеживание изменений cookie
     */
    startCookiePolling() {
        let lastCookieTheme = this.getCookie(this.COOKIE_KEY);
        
        setInterval(() => {
            const currentCookieTheme = this.getCookie(this.COOKIE_KEY);
            
            if (currentCookieTheme !== lastCookieTheme) {
                lastCookieTheme = currentCookieTheme;
                const newTheme = currentCookieTheme || this.themes.light;
                
                // Применяем новую тему и обновляем localStorage
                if (newTheme !== this.getCurrentTheme()) {
                    localStorage.setItem(this.STORAGE_KEY, newTheme);
                    this.applyTheme(newTheme, false);
                }
            }
        }, 500); // Проверяем каждые 500мс
    }

    setCookie(name, value, days) {
        const expires = new Date();
        expires.setTime(expires.getTime() + (days * 24 * 60 * 60 * 1000));
        document.cookie = `${name}=${value};expires=${expires.toUTCString()};path=/;SameSite=Lax`;
    }

    getCookie(name) {
        const nameEQ = name + "=";
        const ca = document.cookie.split(';');
        for(let i = 0; i < ca.length; i++) {
            let c = ca[i];
            while (c.charAt(0) === ' ') c = c.substring(1, c.length);
            if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
        }
        return null;
    }

    /**
     * Немедленное применение темы для предотвращения FOUC
     */
    applyThemeImmediately() {
        // Тема уже применена в IIFE выше
        const cookieTheme = this.getCookie(this.COOKIE_KEY);
        const savedTheme = cookieTheme || localStorage.getItem(this.STORAGE_KEY) || this.themes.light;
        
        // Убеждаемся в синхронизации
        if (cookieTheme && cookieTheme !== localStorage.getItem(this.STORAGE_KEY)) {
            localStorage.setItem(this.STORAGE_KEY, cookieTheme);
        } else if (!cookieTheme && localStorage.getItem(this.STORAGE_KEY)) {
            this.setCookie(this.COOKIE_KEY, localStorage.getItem(this.STORAGE_KEY), 365);
        }
    }

    /**
     * Инициализация компонентов после загрузки DOM
     */
    initializeComponents() {
        this.loadLogoUrls();
        this.findThemeSwitcher();
        this.initMobileMenu();
        
        // Применяем текущую тему с обновлением UI
        const currentTheme = this.getCurrentTheme();
        this.applyTheme(currentTheme, false);
        
        console.log('ThemeManager initialized with theme:', currentTheme);
    }

    /**
     * Поиск кнопки переключения темы в вёрстке
     */
    findThemeSwitcher() {
        this.themeSwitcher = document.getElementById('theme-switcher');
        if (this.themeSwitcher) {
            console.log('Theme switcher found in header');
        } else {
            console.warn('Theme switcher not found');
        }
    }

    /**
     * Инициализация мобильного меню
     */
    initMobileMenu() {
        const mobileToggle = document.getElementById('mobileMenuToggle');
        const mobileNav = document.getElementById('mobileNav');
        
        if (mobileToggle && mobileNav) {
            mobileToggle.addEventListener('click', () => {
                mobileToggle.classList.toggle('active');
                mobileNav.classList.toggle('active');
                
                // Блокируем скролл body при открытии меню
                if (mobileNav.classList.contains('active')) {
                    document.body.style.overflow = 'hidden';
                } else {
                    document.body.style.overflow = '';
                }
                
                console.log('Mobile menu toggled');
            });
            
            // Закрытие меню при клике на ссылку
            const navLinks = mobileNav.querySelectorAll('.nav__link:not(.theme-switcher)');
            navLinks.forEach(link => {
                link.addEventListener('click', () => {
                    mobileToggle.classList.remove('active');
                    mobileNav.classList.remove('active');
                    document.body.style.overflow = '';
                });
            });
            
            console.log('Mobile menu initialized');
        } else {
            console.warn('Mobile menu elements not found');
        }
    }

    /**
     * Создание кнопки переключения темы в header
     */
    createThemeSwitcher() {
        // Проверяем, нет ли уже кнопки
        if (document.getElementById('theme-switcher')) {
            this.themeSwitcher = document.getElementById('theme-switcher');
            return;
        }

        // Создаём кнопку
        const switcher = document.createElement('button');
        switcher.id = 'theme-switcher';
        switcher.className = 'theme-switcher';
        switcher.innerHTML = '<i class="fas fa-moon"></i><span>Тёмная тема</span>';
        switcher.title = 'Переключить тему';
        
        // Ищем место для вставки в header
        const header = document.querySelector('.header-content') || 
                      document.querySelector('header') ||
                      document.querySelector('.header');
        
        if (header) {
            header.appendChild(switcher);
            this.themeSwitcher = switcher;
            console.log('Theme switcher created and added to header');
        } else {
            console.warn('Header not found, cannot create theme switcher');
        }
    }

    /**
     * Привязка событий
     */
    bindEvents() {
        if (this.themeSwitcher) {
            this.themeSwitcher.addEventListener('click', () => {
                this.toggleTheme();
            });
            console.log('Theme switcher event bound');
        }
    }

    /**
     * НОВЫЙ МЕТОД: Обеспечение наличия кнопки темы в мобильном меню
     */
    ensureThemeSwitcherInMobileMenu() {
        if (!this.themeSwitcher) return;
        
        // Проверяем размер экрана
        if (window.innerWidth <= 768) {
            const navList = document.querySelector('.nav__list');
            const themeSwitcherParent = this.themeSwitcher.parentElement;
            
            // Если кнопка не в списке навигации, перемещаем её туда
            if (navList && themeSwitcherParent !== navList && !themeSwitcherParent.classList.contains('nav__item')) {
                const listItem = document.createElement('li');
                listItem.className = 'nav__item theme-switcher-item';
                listItem.appendChild(this.themeSwitcher);
                navList.appendChild(listItem);
            }
        }
    }

    /**
     * Получение текущей темы
     */
    getCurrentTheme() {
        const cookieTheme = this.getCookie(this.COOKIE_KEY);
        return cookieTheme || localStorage.getItem(this.STORAGE_KEY) || this.themes.light;
    }

    /**
     * Переключение темы
     */
    toggleTheme() {
        const currentTheme = this.getCurrentTheme();
        const newTheme = currentTheme === this.themes.dark ? this.themes.light : this.themes.dark;
        this.setTheme(newTheme);
    }

    /**
     * Установка конкретной темы
     */
    setTheme(theme) {
        if (!Object.values(this.themes).includes(theme)) {
            console.warn('Unknown theme:', theme);
            theme = this.themes.light;
        }

        this.applyTheme(theme, true);
    }

    /**
     * Загрузка URL логотипов из data-атрибутов
     */
    loadLogoUrls() {
        const logoElement = document.querySelector('.logo, #dynamic-logo');
        if (logoElement) {
            this.logos.light = logoElement.dataset.lightLogo;
            this.logos.dark = logoElement.dataset.darkLogo;
            
            console.log('Logo URLs loaded:', this.logos);
        } else {
            console.warn('Logo element not found');
        }
    }

    /**
     * Обновление логотипа в зависимости от темы с плавной анимацией
     */
    updateLogo(theme) {
        const logoElement = document.getElementById('dynamic-logo');
        
        if (!logoElement) {
            console.warn('Logo element not found');
            return;
        }

        const logoPath = this.logos[theme];

        if (!logoPath) {
            console.warn('Logo path not found for theme:', theme);
            return;
        }

        if (logoElement.src !== logoPath) {
            // Плавная смена логотипа
            logoElement.style.opacity = '0';
            
            setTimeout(() => {
                logoElement.src = logoPath;
                logoElement.style.opacity = '1';
                console.log(`Logo updated to: ${logoPath} for theme: ${theme}`);
            }, 150);
        }
    }

    /**
     * Применение темы
     */
    applyTheme(theme, updateStorage = true) {
        const htmlElement = document.documentElement;
        const bodyElement = document.body;
        const isLight = theme === this.themes.light;

        // Применяем класс темы
        if (isLight) {
            htmlElement.classList.remove(this.DARK_THEME_CLASS);
            if (bodyElement) {
                bodyElement.classList.remove(this.DARK_THEME_CLASS);
            }
        } else {
            htmlElement.classList.add(this.DARK_THEME_CLASS);
            if (bodyElement) {
                bodyElement.classList.add(this.DARK_THEME_CLASS);
            }
        }

        this.updateLogo(theme);

        // Обновляем storage только если требуется
        if (updateStorage) {
            localStorage.setItem(this.STORAGE_KEY, theme);
            this.setCookie(this.COOKIE_KEY, theme, 365);
        }

        this.updateSwitcherUI(theme);
        this.notifyThemeChange(theme);

        console.log('Theme applied:', theme, 'updateStorage:', updateStorage);
    }

    /**
     * Обновление UI переключателя
     */
    updateSwitcherUI(theme) {
        const themeSwitcher = document.getElementById('theme-switcher');
        const textElement = document.getElementById('theme-text');
        
        if (!themeSwitcher) return;
        
        if (theme === this.themes.dark) {
            if (textElement) {
                textElement.textContent = 'Светлая тема';
            } else {
                themeSwitcher.innerHTML = '<span id="theme-text">Светлая тема</span>';
            }
            themeSwitcher.title = 'Переключить на светлую тему';
        } else {
            if (textElement) {
                textElement.textContent = 'Тёмная тема';
            } else {
                themeSwitcher.innerHTML = '<span id="theme-text">Тёмная тема</span>';
            }
            themeSwitcher.title = 'Переключить на тёмную тему';
        }
        
        console.log('Theme switcher UI updated:', theme, textElement?.textContent);
    }

    /**
     * Уведомление об изменении темы
     */
    notifyThemeChange(theme) {
        // Создаём кастомное событие для других компонентов
        const event = new CustomEvent('themeChanged', {
            detail: { theme }
        });
        document.dispatchEvent(event);

        // Для обратной совместимости
        if (window.onThemeChanged && typeof window.onThemeChanged === 'function') {
            window.onThemeChanged(theme);
        }
    }

    /**
     * Проверка, активна ли тёмная тема
     */
    isDarkTheme() {
        return this.getCurrentTheme() === this.themes.dark;
    }

    /**
     * Статический метод для быстрой инициализации
     */
    static init() {
        if (!window.themeManager) {
            window.themeManager = new ThemeManager();
        }
        return window.themeManager;
    }
}

// Автоматическая инициализация
ThemeManager.init();

// Экспорт для использования в других модулях
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ThemeManager;
}

