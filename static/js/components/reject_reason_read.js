document.addEventListener('DOMContentLoaded', function() {

    // Логика для модального окна причины отказа
    let pendingForm = null;
    let pendingStatusValue = null;

    // Перехват клика по кнопке "Обновить статус"
    document.querySelectorAll('.update-status-btn').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            // document.getElementById('rejectionReasonInput').value = '';
            document.getElementById('rejectionReasonModal').style.display = 'block';
            document.getElementById('rejectionReasonInput').focus();
        });
    });

    document.getElementById('closeRejectionModal').onclick = function() {
        document.getElementById('rejectionReasonModal').style.display = 'none';
        pendingForm = null;
    };

    window.onclick = function(event) {
        const modal = document.getElementById('rejectionReasonModal');
        if (event.target === modal) {
            modal.style.display = 'none';
            pendingForm = null;
        }
    };
});