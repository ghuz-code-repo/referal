$(function() {
  $("#passport_date").datepicker({
    dateFormat: "yy-mm-dd",
    changeMonth: true,
    changeYear: true,
    yearRange: "2000:2030",
    showButtonPanel: false,
    beforeShow: function(input, inst) {
      setTimeout(function() {
        $(".ui-datepicker-buttonpane").hide();
        $(".ui-datepicker-prev, .ui-datepicker-next").hide();
      }, 0);
    }
  });
  // Универсальная тема для календаря: только цвета меняются
  function applyThemeToDatepicker() {
    if (document.documentElement.classList.contains('dark-theme')) {
      $(".ui-datepicker").removeClass("light-datepicker").addClass("dark-datepicker");
    } else {
      $(".ui-datepicker").removeClass("dark-datepicker").addClass("light-datepicker");
    }
  }
  $(document).on("mouseenter focus", "#passport_date", function() {
    setTimeout(applyThemeToDatepicker, 10);
  });
  document.addEventListener('themeChanged', function() {
    setTimeout(applyThemeToDatepicker, 10);
  });
});

// Функция для инициализации datepicker на динамически появляющихся инпутах
function initReferalDatePickers() {
    $("[id^='referal_passport_date_'], [id^='referal_add_passport_date_']").each(function() {
        var input = $(this);
        // Чтобы не инициализировать повторно
        if (input.data('datepicker-initialized')) {
            return;
        }
        console.log("datepicker: найден инпут", input.attr('id'));
        // Проверка поддержки input[type=date]
        var test = document.createElement('input');
        test.setAttribute('type', 'date');
        var isDateSupported = (test.type === 'date');
        // Принудительно инициализируем jQuery UI datepicker даже если type="date" поддерживается
        input.removeAttr('readonly');
        input.attr('type', 'text');
        input.datepicker({
            dateFormat: "yy-mm-dd",
            changeMonth: true,
            changeYear: true,
            yearRange: "2000:2030",
            showButtonPanel: false,
            beforeShow: function(inputEl, inst) {
                setTimeout(function() {
                    $(".ui-datepicker-buttonpane").hide();
                    $(".ui-datepicker-prev, .ui-datepicker-next").hide();
                    console.log("datepicker: beforeShow для", inputEl.id);
                }, 0);
            },
            onSelect: function(dateText, inst) {
                console.log("datepicker: выбрана дата", dateText, "для", input.attr('id'));
            }
        });
        input.attr('readonly', 'readonly');
        input.data('datepicker-initialized', true);
        input.off("focus.dpforce mousedown.dpforce").on("focus.dpforce mousedown.dpforce", function(e) {
            console.log("datepicker: focus/mousedown на", input.attr('id'));
            if ($(".ui-datepicker:visible").length === 0) {
                $(this).datepicker("show");
                console.log("datepicker: show вызван для", input.attr('id'));
            }
        });
        function applyThemeToDatepicker() {
            if (document.documentElement.classList.contains('dark-theme')) {
                $(".ui-datepicker").removeClass("light-datepicker").addClass("dark-datepicker");
            } else {
                $(".ui-datepicker").removeClass("dark-datepicker").addClass("light-datepicker");
            }
            console.log("datepicker: применена тема для", input.attr('id'));
        }
        input.on("focus mouseenter", function() {
            setTimeout(applyThemeToDatepicker, 10);
        });
        document.addEventListener('themeChanged', function() {
            setTimeout(applyThemeToDatepicker, 10);
        });
    });
}

// Инициализация при загрузке страницы
$(function() {
    // ...existing code for #passport_date...
    initReferalDatePickers();
});

// Переинициализация при каждом открытии модального окна (если используется динамическое создание)
document.addEventListener('DOMContentLoaded', function() {
    // Если ваши модальные окна открываются через кастомные события, подпишитесь на них:
    $(document).on('click', '.open_document_form', function() {
        setTimeout(initReferalDatePickers, 100); // чуть позже, чтобы DOM успел обновиться
    });
    // Если используется MutationObserver или другой способ динамического добавления — вызовите initReferalDatePickers() после появления инпута
});
