/**
 * Валидация паролей для админ панели
 */
function validatePassword() {
    var password = document.getElementById("password");
    var confirm_password = document.getElementById("confirm_password");
    var message = document.getElementById("password-message");
    
    if (!password || !confirm_password || !message) return;
    
    var submitBtn = message.parentElement.querySelector("button[type='submit']");
    
    if (password.value && confirm_password.value) {
        if (password.value !== confirm_password.value) {
            message.style.display = "block";
            if (submitBtn) submitBtn.disabled = true;
        } else {
            message.style.display = "none";
            if (submitBtn) submitBtn.disabled = false;
        }
    }
}

/**
 * Инициализация валидации паролей
 */
function initPasswordValidation() {
    const passwordInputs = document.querySelectorAll('#password, #confirm_password');
    passwordInputs.forEach(input => {
        input.addEventListener('input', validatePassword);
    });
}
