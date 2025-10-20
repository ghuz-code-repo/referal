document.addEventListener('DOMContentLoaded', function() {

    // Логика для модального окна причины отказа
    let pendingForm = null;
    let pendingStatusValue = null;

    // Перехват клика по кнопке "Обновить статус"
    document.querySelectorAll('.update-status-btn').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            const form = btn.closest('form');
            const select = form.querySelector('.status-select');
            if (select && select.value == '500') { // 500 - отказ
                e.preventDefault();
                pendingForm = form;
                pendingStatusValue = select.value;
                // document.getElementById('rejectionReasonInput').value = '';
                document.getElementById('rejectionReasonModal').style.display = 'block';
                document.getElementById('rejectionReasonInput').focus();
            } else {
                // Если не отказ, отправляем форму обычным образом
                form.submit();
            }
        });
    });

    // Проверяем существование элементов модального окна перед установкой обработчиков
    const submitButton = document.getElementById('submitRejectionReason');
    const closeButton = document.getElementById('closeRejectionModal');
    const modal = document.getElementById('rejectionReasonModal');

    if (submitButton) {
        submitButton.onclick = function() {
            const reasonInput = document.getElementById('rejectionReasonInput');
            if (!reasonInput) return;
            
            const reason = reasonInput.value.trim();
            if (!reason) {
                reasonInput.focus();
                return;
            }
            if (pendingForm) {
                // Добавляем скрытое поле с причиной отказа
                let hidden = pendingForm.querySelector('input[name="rejection_reason"]');
                if (!hidden) {
                    hidden = document.createElement('input');
                    hidden.type = 'hidden';
                    hidden.name = 'rejection_reason';
                    pendingForm.appendChild(hidden);
                }
                hidden.value = reason;
                if (modal) modal.style.display = 'none';
                pendingForm.submit();
                pendingForm = null;
            }
        };
    }

    if (closeButton) {
        closeButton.onclick = function() {
            if (modal) modal.style.display = 'none';
            pendingForm = null;
        };
    }

    if (modal) {
        window.onclick = function(event) {
            if (event.target === modal) {
                modal.style.display = 'none';
                pendingForm = null;
            }
        };
    }
});