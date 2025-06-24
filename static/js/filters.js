document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.clear-filter-btn').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            const filterName = btn.getAttribute('data-filter');
            // Найти input/select с этим именем
            const input = document.querySelector(`[name="${filterName}"]`);
            if (input) {
                if (input.tagName === 'SELECT') {
                    input.selectedIndex = 0;
                } else {
                    input.value = '';
                }
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
            // Найти ближайшую форму
            let form = btn.closest('form');
            if (form) {
                // Сохраняем текущий url формы
                const action = form.getAttribute('action');
                // Если action не задан, используем текущий location.pathname + search
                if (!action || action === '') {
                    form.setAttribute('action', window.location.pathname + window.location.search);
                }
                form.submit();
            }
        });
    });
});