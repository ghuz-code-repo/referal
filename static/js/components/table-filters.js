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
    
    // Обработка кнопок сортировки
    const sortButtons = document.querySelectorAll('.sort-btn');
    sortButtons.forEach(button => {
        button.addEventListener('click', function() {
            const field = this.dataset.field;
            addSort(field);
        });
    });
    
    // Обработка кнопок очистки фильтров
    const clearFilterButtons = document.querySelectorAll('.clear-filter-btn');
    clearFilterButtons.forEach(button => {
        button.addEventListener('click', function() {
            const filter = this.dataset.filter;
            clearFilter(filter);
        });
    });
    
    // Обработка кнопок очистки сортировки
    const clearSortButtons = document.querySelectorAll('.clear-sort-btn');
    clearSortButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.stopPropagation(); // Предотвращаем срабатывание других обработчиков
            const field = this.dataset.field;
            removeSort(field);
        });
    });
    
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
    
    function addSort(field) {
        const url = new URL(window.location);
        const params = new URLSearchParams(url.search);
        
        // Получаем текущую сортировку
        let currentSort = params.get('sort') || '';
        let sortFields = [];
        
        if (currentSort) {
            sortFields = currentSort.split(',').map(item => {
                const [f, order] = item.split(':');
                return { field: f, order: order };
            });
        }
        
        // Ищем, есть ли уже сортировка по этому полю
        const existingIndex = sortFields.findIndex(s => s.field === field);
        
        if (existingIndex !== -1) {
            // Поле уже есть в сортировке - только меняем направление
            const current = sortFields[existingIndex];
            if (current.order === 'asc') {
                sortFields[existingIndex].order = 'desc';
            } else {
                sortFields[existingIndex].order = 'asc';
            }
        } else {
            // Добавляем новое поле (по умолчанию asc)
            sortFields.push({ field: field, order: 'asc' });
        }
        
        // Формируем новую строку сортировки
        const sortString = sortFields.map(s => `${s.field}:${s.order}`).join(',');
        params.set('sort', sortString);
        
        params.set('page', '1'); // Сбрасываем на первую страницу
        
        url.search = params.toString();
        window.location.href = url.toString();
    }
    
    function clearFilter(filterName) {
        const url = new URL(window.location);
        const params = new URLSearchParams(url.search);
        
        params.delete(filterName);
        params.set('page', '1');
        
        url.search = params.toString();
        window.location.href = url.toString();
    }
    
    function removeSort(field) {
        const url = new URL(window.location);
        const params = new URLSearchParams(url.search);
        
        // Получаем текущую сортировку
        let currentSort = params.get('sort') || '';
        let sortFields = [];
        
        if (currentSort) {
            sortFields = currentSort.split(',').map(item => {
                const [f, order] = item.split(':');
                return { field: f, order: order };
            });
        }
        
        // Убираем указанное поле из сортировки
        sortFields = sortFields.filter(s => s.field !== field);
        
        // Формируем новую строку сортировки
        if (sortFields.length > 0) {
            const sortString = sortFields.map(s => `${s.field}:${s.order}`).join(',');
            params.set('sort', sortString);
        } else {
            params.delete('sort');
        }
        
        params.set('page', '1');
        
        url.search = params.toString();
        window.location.href = url.toString();
    }
});