# TODO: Добавление полей в MacroCRM

## Необходимо добавить в таблицу estate_deals_contacts следующие поля:

1. `passport_number` - Серия и номер паспорта
2. `passport_giver` - Кем выдан паспорт  
3. `passport_date` - Дата выдачи паспорта
4. `passport_address` - Адрес прописки
5. `email` - Email адрес

## После добавления полей в MacroCRM нужно:

1. Обновить SQL запрос в `services/data_sync_service.py` - раскомментировать строки с TODO
2. Убрать "(TODO: добавить в MacroCRM)" из шаблонов
3. Обновить JavaScript валидацию в `macro-transfer.js`
4. Запустить синхронизацию данных для получения новых полей

## Файлы, которые нужно будет обновить:

- `services/data_sync_service.py` - раскомментировать получение новых полей
- `templates/modals/document_form_modal.html` - убрать TODO сообщения
- `static/js/components/macro-transfer.js` - убрать проверки на TODO
