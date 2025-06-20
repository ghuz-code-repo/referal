document.addEventListener('DOMContentLoaded', function() {
    // Обработка фильтров в шапке таблицы
    const filterInputs = document.querySelectorAll('.header-filter');
    let filterTimeout;
    
    filterInputs.forEach(input => {
        input.addEventListener('input', function() {
            clearTimeout(filterTimeout);
            filterTimeout = setTimeout(() => {
                applyFilters();
            }, 300); // Задержка 300мс для избежания лишних запросов
        });
        
        input.addEventListener('change', function() {
            applyFilters();
        });
    });
    
    // Обработка изменения количества элементов на странице
    const perPageSelect = document.getElementById('per_page_select');
    if (perPageSelect) {
        perPageSelect.addEventListener('change', function() {
            applyFilters();
        });
    }
    
    function applyFilters() {
        const url = new URL(window.location);
        const params = new URLSearchParams(url.search);
        
        // Сбрасываем страницу на первую при применении фильтров
        params.set('page', '1');
        
        // Собираем значения фильтров
        filterInputs.forEach(input => {
            const filterName = input.dataset.filter;
            const value = input.value.trim();
            
            if (value) {
                params.set(filterName, value);
            } else {
                params.delete(filterName);
            }
        });
        
        // Обрабатываем выбор количества элементов
        if (perPageSelect) {
            params.set('per_page', perPageSelect.value);
        }
        
        // Перенаправляем с новыми параметрами
        url.search = params.toString();
        window.location.href = url.toString();
    }
});
