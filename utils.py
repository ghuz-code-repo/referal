"""Утилиты для приложения - только необходимые функции"""

import base64
from datetime import datetime
import threading
import time
import os
import re
from typing import List, Optional, Tuple

from flask import current_app, logging
import requests


def _get_api_headers():
    """Get headers with X-API-Key for auth-service /api/* calls"""
    from flask import current_app
    auth_client = getattr(current_app, 'auth_client', None)
    if auth_client and hasattr(auth_client, 'api_headers'):
        return auth_client.api_headers
    api_key = os.getenv('INTERNAL_API_KEY', '')
    return {'X-API-Key': api_key} if api_key else {}


# Вспомогательная функция для запуска задач в отдельном потоке с контекстом Flask
def run_async_task(func, *args, **kwargs):
    app_context = None
    try:
        # Попытка получить текущий контекст приложения, если он существует
        if current_app:
            app_context = current_app.app_context()
            app_context.push()
        func(*args, **kwargs)
    except Exception as e:
        # Здесь вы можете добавить логирование ошибки,
        # например, using current_app.logger.error(f"Async task failed: {e}")
        # Но учтите, что current_app может быть недоступен здесь без app_context()
        print(f"Ошибка в асинхронной задаче {func.__name__}: {e}")
    finally:
        if app_context:
            app_context.pop()


def month_name_genitive(month_number):
    """Возвращает название месяца в родительном падеже"""
    months = {
        1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
        5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
        9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
    }
    return months.get(month_number, '')


def clean_phone_number(phone: str) -> str:
    """Очищает номер телефона от лишних символов"""
    if not phone:
        return ""
    # Убираем все кроме цифр и знака +
    return re.sub(r'[^\d+]', '', phone.strip())


def extract_and_normalize_phones(phone_field: str) -> list:
    """
    Извлекает и нормализует все номера телефонов из строки.
    Обрабатывает различные форматы:
    - 9989773824501 (без разделителей)
    - +998.974031753 (с точками)
    - (+998.981154200,+998.914093336) (несколько телефонов в скобках через запятую)
    - +998 90 315 84 14 (с пробелами)
    
    Возвращает список всех уникальных вариантов нормализованных номеров для поиска.
    """
    if not phone_field:
        return []
    
    phones = []
    
    # Удаляем внешние скобки если есть
    phone_field = phone_field.strip()
    if phone_field.startswith('(') and phone_field.endswith(')'):
        phone_field = phone_field[1:-1]
    
    # Разделяем по запятым для случая с несколькими номерами
    phone_parts = [p.strip() for p in phone_field.split(',')]
    
    for part in phone_parts:
        if not part:
            continue
        
        # Убираем точки, пробелы, скобки, дефисы - оставляем только + и цифры
        clean = re.sub(r'[^\d+]', '', part)
        
        if not clean or len(clean) < 9:
            continue
        
        # Генерируем варианты для поиска
        variants = set()
        
        # Вариант 1: как есть после очистки
        variants.add(clean)
        
        # Вариант 2: добавляем + в начало если нет
        if not clean.startswith('+'):
            variants.add('+' + clean)
        
        # Вариант 3: убираем + если есть
        if clean.startswith('+'):
            variants.add(clean[1:])
        
        # Вариант 4: для узбекских номеров - стандартизация
        # Если начинается с 998 или +998
        if clean.startswith('+998') or clean.startswith('998'):
            # Извлекаем основную часть (9 цифр после 998)
            digits = clean.replace('+', '').replace('998', '', 1)
            if len(digits) == 9:
                # Добавляем все варианты
                variants.add('998' + digits)  # 9989XXXXXXXX
                variants.add('+998' + digits)  # +9989XXXXXXXX
                variants.add(digits)  # 9XXXXXXXX (без кода страны)
                # НОВОЕ: добавляем формат С ПРОБЕЛАМИ для поиска в MacroContact
                variants.add(f"+998 {digits[:2]} {digits[2:5]} {digits[5:7]} {digits[7:9]}")  # +998 XX XXX XX XX
        
        # Вариант 5: если номер начинается с 9 и длина 12-13 цифр (998 + 9 цифр)
        elif clean.startswith('9') and len(clean) >= 12:
            # Возможно это 9989XXXXXXXX без +
            if clean[:3] == '998':
                digits = clean[3:]
                if len(digits) == 9:
                    variants.add(clean)  # 9989XXXXXXXX
                    variants.add('+' + clean)  # +9989XXXXXXXX
                    variants.add('998' + digits)  # на случай если код дублируется
        
        phones.extend(variants)
    
    # Убираем дубликаты и возвращаем
    return list(set(phones))


def format_phone_number(phone: str) -> Optional[str]:
    """Форматирует номер телефона согласно стандартам"""
    if not phone:
        return None
    
    # Очищаем номер
    clean_phone = clean_phone_number(phone)
    
    # Обработка узбекских номеров (+998)
    if clean_phone.startswith('+998') or clean_phone.startswith('998'):
        return format_998_number(clean_phone)
    
    # Обработка российских номеров (+7)
    elif clean_phone.startswith('+7') or (clean_phone.startswith('7') and len(clean_phone) >= 11):
        return format_7_number(clean_phone)
    
    # Обработка других международных номеров
    elif clean_phone.startswith('+'):
        return format_international_number(clean_phone)
    
    # Если нет кода страны, но номер длинный и начинается с 998
    elif len(clean_phone) >= 11 and clean_phone.startswith('998'):
        return format_998_number(clean_phone)
    
    # Если номер из 9 цифр, добавляем +998
    elif len(clean_phone) == 9 and clean_phone.isdigit():
        uzbek_prefixes = ['90', '91', '93', '94', '95', '97', '98', '99', '77', '88', '33', '50', '55', '71']
        if clean_phone[:2] in uzbek_prefixes:
            return format_998_number('+998' + clean_phone)
    
    return None


def format_998_number(phone: str) -> Optional[str]:
    """Форматирует узбекский номер как +998 XX XXX XX XX"""
    # Убираем +998 если есть
    if phone.startswith('+998'):
        digits = phone[4:]
    elif phone.startswith('998'):
        digits = phone[3:]
    else:
        digits = phone
    
    # Убираем все не-цифры
    digits = re.sub(r'\D', '', digits)
    
    # Стандартный 9-значный номер
    if len(digits) == 9:
        return f"+998 {digits[:2]} {digits[2:5]} {digits[5:7]} {digits[7:9]}"
    
    # Обработка 12-значных номеров (99XXXXXXXXX -> +998 XX XXX XX XX)
    if len(digits) == 12 and digits.startswith('99'):
        return f"+998 {digits[2:4]} {digits[4:7]} {digits[7:9]} {digits[9:11]}"
    
    # Обработка 13-значных номеров начинающихся с 998
    if len(digits) == 13 and digits.startswith('998'):
        return f"+998 {digits[3:5]} {digits[5:8]} {digits[8:10]} {digits[10:12]}"
    
    # Обработка 11-значных номеров начинающихся с 99
    if len(digits) == 11 and digits.startswith('99'):
        return f"+998 {digits[2:4]} {digits[4:7]} {digits[7:9]} {digits[9:11]}"
    
    # Обработка 10-значных номеров начинающихся с 98
    if len(digits) == 10 and digits.startswith('98'):
        return f"+998 9{digits[2:4]} {digits[4:7]} {digits[7:9]} {digits[9]}"
    
    return None


def format_7_number(phone: str) -> Optional[str]:
    """Форматирует российский номер как +7 XXX XXX XX XX"""
    # Обработка точечного формата
    dotted_match = re.match(r'^\+7\.(\d+)$', phone)
    if dotted_match:
        digits = dotted_match.group(1)
    else:
        # Убираем +7 или 7
        if phone.startswith('+7'):
            digits = phone[2:]
        elif phone.startswith('7') and len(phone) > 1:
            digits = phone[1:]
        else:
            digits = phone
    
    # Убираем все не-цифры
    digits = re.sub(r'\D', '', digits)
    
    # Должно быть ровно 10 цифр
    if len(digits) == 10:
        return f"+7 {digits[:3]} {digits[3:6]} {digits[6:8]} {digits[8:10]}"
    
    # Если цифр больше 10, берем первые 10
    if len(digits) > 10:
        digits = digits[:10]
        return f"+7 {digits[:3]} {digits[3:6]} {digits[6:8]} {digits[8:10]}"
    
    return None


def format_international_number(phone: str) -> Optional[str]:
    """Форматирует международные номера"""
    # Обработка формата +X.XXXXXXXXXX
    match = re.match(r'^\+(\d{1,3})\.(\d+)$', phone)
    if match:
        country_code, number = match.groups()
        if country_code == '1':
            return f"+{country_code} {number[:3]} {number[3:6]} {number[6:]}"
        elif len(country_code) == 2:
            return f"+{country_code} {number[:3]} {number[3:6]} {number[6:]}"
        elif len(country_code) == 3:
            return f"+{country_code} {number[:2]} {number[2:5]} {number[5:]}"
    
    # Стандартный международный формат
    if phone.startswith('+'):
        digits = re.sub(r'\D', '', phone[1:])
        if 7 <= len(digits) <= 15:
            country_code = digits[:3] if len(digits) > 10 else digits[:2]
            number = digits[len(country_code):]
            return f"+{country_code} {number}"
    
    return None

def _send_sms_sync(phone_number, user_full_name):
    """
    Внутренняя функция для синхронной отправки SMS-сообщения через Playmobile API.
    Предназначена для вызова из send_sms_async.
    """
    # Clean the phone number - remove spaces and ensure it starts with "+998"
    clean_phone = phone_number.replace(" ", "").replace("+", "")
    if not clean_phone.startswith("998"):
        print(f"Invalid phone number format: {phone_number}")
        # Можно использовать current_app.logger.error, если контекст доступен
        return False
        
    # Ensure user_full_name is properly decoded from Base64 if needed
    # (This is handled in routes.py, but added here for robustness)
    if isinstance(user_full_name, bytes):
        try:
            user_full_name = user_full_name.decode('utf-8')
        except UnicodeDecodeError:
            # Try to decode base64
            try:
                user_full_name = base64.b64decode(user_full_name).decode('utf-8')
            except:
                pass   # Keep as is if all decoding attempts fail
    
    # SMS text with recommendation
    sms_text = f"Вы были рекомендованы {user_full_name}. Вам предоставлена персональная скидка. Уточните удобное место и время встречи по номеру {os.getenv('GH_PHONE_NUMBER')}"
    
    # Playmobile API configuration
    api_url = os.getenv('SMS_API_URL')

    # Your Playmobile credentials
    username = os.getenv('SMS_API_USERNAME')
    password = os.getenv('SMS_API_PASSWORD')
    originator = os.getenv('SMS_API_ORIGINATOR')
    message_id = (datetime.now().strftime("%Y%m%d%H%M%S").encode('utf-8')).decode('utf-8')   # Unique message ID
    
    # Format payload according to Playmobile's requirements
    payload = {
        "messages": [
            {
                "recipient": clean_phone,   # Correctly formatted
                "message-id": message_id,
                "sms": {
                    "originator": originator,   # Ensure this is a string
                    "content": {
                        "text": sms_text
                    }
                }
            }
        ]
    }
    
    try:
        userpass = username + ':' + password
        b64Val = base64.b64encode(userpass.encode('utf-8')).decode('utf-8')

        headers = {
            "Authorization": "Basic %s" % b64Val,
            "Content-Type": "application/json",
            "charset": "UTF-8"   # Explicitly set charset as mentioned in docs
        }

        response = requests.post(api_url, headers=headers, json=payload, timeout=30)

        print(f"Response status: {response.status_code}")
        print(f"Response text: {response.text}")

        if response.status_code == 200:
            print(f"SMS sent successfully to {phone_number}")
            return True
        else:
            print(f"Failed to send SMS: {response.status_code} - {response.text}")
            return False
        
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Playmobile: {e}")
        return False
    
def send_sms(phone_number, user_full_name):
    """
    Запускает отправку SMS в отдельном потоке.
    """
    thread = threading.Thread(target=run_async_task, args=(_send_sms_sync, phone_number, user_full_name))
    thread.daemon = True # Позволяет программе завершиться, даже если поток еще работает
    thread.start()


def staff_recipient(role_key):
    """
    Определить получателя-сотрудника по ключу роли.

    Сотрудник — пользователь портала, поэтому адресуем его логином: адрес доставки
    держит auth-service, и смена почты сотрудника не требует правки .env сервиса.
    Пока логин не прописан, работает прежний вариант с адресом из .env.

    Args:
        role_key (str): префикс переменных окружения, например 'MAIN_ADMIN'
                        (читаются MAIN_ADMIN_LOGIN и MAIN_ADMIN_EMAIL)

    Returns:
        dict: kwargs адресации для notification_client.send_email, либо пустой dict,
              если ни логин, ни адрес не заданы
    """
    login = os.getenv(f'{role_key}_LOGIN')
    if login:
        return {'login': login}

    email = os.getenv(f'{role_key}_EMAIL')
    if email:
        return {'external_recipient': email}

    return {}


def send_email_to_staff(role_key, subject, body):
    """
    Отправить письмо сотруднику, заданному переменными окружения `<role_key>_LOGIN`
    или `<role_key>_EMAIL`. Отправка идёт в отдельном потоке.

    Returns:
        bool: False, если получатель не настроен и письмо даже не поставлено в очередь
    """
    addressing = staff_recipient(role_key)
    if not addressing:
        print(f"⚠️ Получатель {role_key} не настроен: задайте {role_key}_LOGIN или {role_key}_EMAIL")
        return False

    send_email(subject=subject, body=body, **addressing)
    return True


def _send_email_sync(subject, body, login=None, external_recipient=None):
    """
    Внутренняя функция для синхронной отправки email через Notification Service.
    Предназначена для вызова из send_email.

    Получателя задаёт либо login (пользователь портала), либо external_recipient.
    """
    from notification_client import get_notification_client

    target = login or external_recipient

    try:
        # Получаем клиент notification service
        notification_client = get_notification_client()

        # Отправляем основное письмо получателю
        success = notification_client.send_email(
            subject=subject,
            body=body,
            login=login,
            external_recipient=external_recipient,
        )

        if success:
            print(f"Email queued for sending to {target}")

            # Отправляем уведомление администратору об успешной отправке
            admin = staff_recipient('MAIN_ADMIN')
            if admin:
                admin_subject = f'Ответственное лицо реферальной программы {target} получило письмо'
                admin_body = f'Письмо отправлено {target} с темой {subject}\nтело:\n{body}'
                notification_client.send_email(
                    subject=admin_subject,
                    body=admin_body,
                    **admin
                )
                print("Admin notification queued")

            print(f"Email sent successfully via Notification Service: {target} {subject}")
        else:
            raise Exception("Notification service returned failure status")

    except Exception as e:
        print(f"Failed to send email via Notification Service: {e}")

        # Отправляем уведомление администратору об ошибке
        try:
            admin = staff_recipient('MAIN_ADMIN')
            if admin:
                notification_client = get_notification_client()
                admin_subject = f'Ответственное лицо реферальной программы {target} НЕ получило письмо'
                admin_body = f'Письмо не было отправлено {target} с темой {subject}\nтело:\n{body}\nОшибка {e}'
                notification_client.send_email(
                    subject=admin_subject,
                    body=admin_body,
                    **admin
                )
                print("Error notification sent to admin")
        except Exception as admin_error:
            print(f"Failed to send error notification to admin: {admin_error}")


def send_email(subject, body, login=None, external_recipient=None):
    """
    Запускает отправку email в отдельном потоке.

    Args:
        subject: тема письма
        body: тело письма
        login: логин получателя на портале (предпочтительно)
        external_recipient: адрес получателя вне портала
    """
    thread = threading.Thread(
        target=run_async_task,
        args=(_send_email_sync, subject, body),
        kwargs={'login': login, 'external_recipient': external_recipient},
    )
    thread.daemon = True  # Позволяет программе завершиться, даже если поток еще работает
    thread.start()


def sync_user_data_from_auth_service(user, force_sync=False, headers=None):
    """
    Синхронизирует данные пользователя из auth-service.
    
    Args:
        user: Объект пользователя из referal сервиса
        force_sync: Принудительная синхронизация даже если данные уже есть
        headers: Request headers для fallback данных (phone, email)
    
    Returns:
        bool: True если синхронизация прошла успешно
    """
    from models import UserData, db
    
    try:
        # Импортируем auth_client из app контекста
        from flask import current_app
        auth_client = getattr(current_app, 'auth_client', None)
        
        if not auth_client:
            print("AuthClient not available")
            return False
        
        # Проверяем наличие auth_user_id
        if not hasattr(user, 'auth_user_id') or not user.auth_user_id:
            print(f"❌ User {user.login} does not have auth_user_id set, skipping sync")
            print(f"   User object: id={user.id}, login={user.login}, has auth_user_id attr: {hasattr(user, 'auth_user_id')}")
            if hasattr(user, 'auth_user_id'):
                print(f"   auth_user_id value: '{user.auth_user_id}'")
            return False
            
        # Проверяем, есть ли уже данные пользователя
        user_data = UserData.query.filter_by(user_id=user.id).first()
        
        print(f"🔄 Syncing user data for {user.login} (auth_user_id: {user.auth_user_id})")
        print(f"   UserData exists: {user_data is not None}, force_sync: {force_sync}")
        
        # Если данные есть и принудительная синхронизация не требуется, пропускаем
        # Получаем данные профиля из auth-service
        profile_url = f"/api/users/{user.auth_user_id}/profile"
        print(f"📡 Fetching profile from: {auth_client.auth_service_url.rstrip('/')}{profile_url}")
        try:
            profile_response = requests.get(
                f"{auth_client.auth_service_url.rstrip('/')}{profile_url}",
                headers=_get_api_headers(),
                timeout=5
            )
            
            print(f"   Response status: {profile_response.status_code}")
            
            if profile_response.status_code != 200:
                print(f"   ❌ Failed to fetch profile: {profile_response.text[:200]}")
                return False
        except Exception as e:
            print(f"   ❌ Exception fetching profile: {e}")
            return False
            
        profile_data = profile_response.json()
        
        print(f"📥 Profile data from auth-service: {profile_data}")
        
        # Создаем или обновляем UserData
        if not user_data:
            user_data = UserData(user_id=user.id)
            db.session.add(user_data)
        
        # Получаем компоненты ФИО из auth-service
        last_name = profile_data.get('last_name', '').strip()
        first_name = profile_data.get('first_name', '').strip()
        middle_name = profile_data.get('middle_name', '').strip()
        suffix = profile_data.get('suffix', '').strip()
        
        # Сохраняем компоненты
        user_data.last_name = last_name
        user_data.first_name = first_name
        user_data.middle_name = middle_name
        
        # ФОРМИРУЕМ ПОЛНОЕ ИМЯ: Фамилия Имя Отчество Частица
        name_parts = []
        if last_name:
            name_parts.append(last_name)
        if first_name:
            name_parts.append(first_name)
        if middle_name:
            name_parts.append(middle_name)
        if suffix:
            name_parts.append(suffix)
        
        user_data.full_name = ' '.join(name_parts) if name_parts else profile_data.get('full_name', '')
        
        # Синхронизируем только основные данные профиля (НЕ документы)
        user_data.phone = profile_data.get('phone') or profile_data.get('phone_number', '')
        user_data.e_mail = profile_data.get('email') or profile_data.get('e_mail', '')
        
        # ❌ DEPRECATED: Documents are NOT synced to local DB anymore
        # Documents should be fetched from Auth-Service API in real-time:
        # - Via headers (X-User-Passport-*, X-User-Bank-*, X-User-PINFL)
        # - Via API: /api/users/{user_id}/documents/for-service/referal
        # See app_with_auth_connector.py:get_user_documents_from_auth_service()
        
        # Parse birth_date if present
        if profile_data.get('birth_date'):
            try:
                user_data.birth_date = datetime.fromisoformat(
                    profile_data['birth_date'].replace('Z', '+00:00')
                ).date()
            except (ValueError, AttributeError):
                pass
        
        # Fallback на заголовки если данные не пришли из API
        if headers and not user_data.phone:
            header_phone = headers.get('X-User-Phone')
            if header_phone:
                user_data.phone = header_phone
                print(f"   📞 Using phone from headers: {header_phone}")
        
        if headers and not user_data.e_mail:
            header_email = headers.get('X-User-Email')
            if header_email:
                user_data.e_mail = header_email
                print(f"   📧 Using email from headers: {header_email}")
        
        db.session.commit()
        print(f"✅ Successfully synced user data for {user.login}")
        print(f"   Last name: {last_name}")
        print(f"   First name: {first_name}")
        print(f"   Middle name: {middle_name}")
        print(f"   Suffix: {suffix}")
        print(f"   ➡️ FULL NAME (constructed): {user_data.full_name}")
        print(f"   Phone: {user_data.phone}")
        print(f"   Email: {user_data.e_mail}")
        print(f"   PINFL: {user_data.pinfl}")
        print(f"   Passport: {user_data.passport_number}")
        return True
        
    except Exception as e:
        print(f"Error syncing user data from auth-service: {e}")
        db.session.rollback()
        return False


def get_user_full_name_from_auth(user):
    """
    Получает актуальное полное имя пользователя из auth-service.
    
    Args:
        user: Объект пользователя из referal сервиса
        
    Returns:
        str: Полное имя пользователя из auth-service или fallback значение
    """
    from flask import current_app
    
    # Сначала пытаемся получить из auth-service
    try:
        auth_client = getattr(current_app, 'auth_client', None)
        
        if not auth_client or not hasattr(user, 'auth_user_id') or not user.auth_user_id:
            # Fallback к локальным данным
            if hasattr(user, 'user_data') and user.user_data and user.user_data.full_name:
                return user.user_data.full_name
            return user.login if hasattr(user, 'login') else "Неизвестно"
        
        # Получаем данные из auth-service
        profile_url = f"/api/users/{user.auth_user_id}/profile"
        profile_response = requests.get(
            f"{auth_client.auth_service_url.rstrip('/')}{profile_url}",
            headers=_get_api_headers(),
            timeout=3  # Короткий timeout для быстрого ответа
        )
        
        if profile_response.status_code == 200:
            profile_data = profile_response.json()
            
            # ФОРМИРУЕМ ПОЛНОЕ ИМЯ ИЗ ОТДЕЛЬНЫХ ПОЛЕЙ: Фамилия Имя Отчество Частица
            last_name = profile_data.get('last_name', '').strip()
            first_name = profile_data.get('first_name', '').strip()
            middle_name = profile_data.get('middle_name', '').strip()
            suffix = profile_data.get('suffix', '').strip()
            
            name_parts = []
            if last_name:
                name_parts.append(last_name)
            if first_name:
                name_parts.append(first_name)
            if middle_name:
                name_parts.append(middle_name)
            if suffix:
                name_parts.append(suffix)
            
            if name_parts:
                return ' '.join(name_parts)
            
            # Fallback к полю full_name если отдельные поля пусты
            full_name = profile_data.get('full_name', '').strip()
            if full_name:
                return full_name
        
    except Exception as e:
        print(f"Warning: Failed to get user full name from auth-service: {e}")
    
    # Fallback к локальным данным
    if hasattr(user, 'user_data') and user.user_data and user.user_data.full_name:
        return user.user_data.full_name
    return user.login if hasattr(user, 'login') else "Неизвестно"


def sync_user_profile_always(user):
    """
    ВСЕГДА синхронизирует данные пользователя из auth-service при каждом запросе.
    Если auth-service недоступен - оставляет локальные данные.
    
    Args:
        user: Объект пользователя из referal сервиса
        
    Returns:
        bool: True если синхронизация прошла успешно
    """
    from models import UserData, db
    from flask import current_app
    
    try:
        auth_client = getattr(current_app, 'auth_client', None)
        
        if not auth_client or not hasattr(user, 'auth_user_id') or not user.auth_user_id:
            print(f"❌ Cannot sync user {user.login}: no auth_client or auth_user_id")
            return False
        
        # Получаем данные профиля из auth-service
        profile_url = f"/api/users/{user.auth_user_id}/profile"
        print(f"🔄 Syncing profile for {user.login} from auth-service...")
        
        profile_response = requests.get(
            f"{auth_client.auth_service_url.rstrip('/')}{profile_url}",
            headers=_get_api_headers(),
            timeout=5
        )
        
        if profile_response.status_code != 200:
            print(f"❌ Failed to fetch profile: HTTP {profile_response.status_code}")
            return False
            
        profile_data = profile_response.json()
        print(f"📥 Profile data from auth-service: {profile_data}")
        print(f"🔍 Checking all keys in profile_data: {list(profile_data.keys())}")
        
        # Получаем или создаем UserData
        user_data = UserData.query.filter_by(user_id=user.id).first()
        if not user_data:
            user_data = UserData(user_id=user.id)
            db.session.add(user_data)
            print(f"📝 Created new UserData for user {user.login}")
        
        # Обновляем данные из auth-service
        user_data.e_mail = profile_data.get('email', '')
        user_data.phone = profile_data.get('phone', '')
        
        # Получаем компоненты ФИО
        last_name = profile_data.get('last_name', '').strip()
        first_name = profile_data.get('first_name', '').strip()
        middle_name = profile_data.get('middle_name', '').strip()
        suffix = profile_data.get('suffix', '').strip()  # Частица (O`G`LI, QIZI и т.д.)
        
        # Сохраняем компоненты
        user_data.last_name = last_name
        user_data.first_name = first_name
        user_data.middle_name = middle_name
        
        # ФОРМИРУЕМ ПОЛНОЕ ИМЯ: Фамилия Имя Отчество Частица
        name_parts = []
        if last_name:
            name_parts.append(last_name)
        if first_name:
            name_parts.append(first_name)
        if middle_name:
            name_parts.append(middle_name)
        if suffix:
            name_parts.append(suffix)
        
        user_data.full_name = ' '.join(name_parts) if name_parts else profile_data.get('full_name', '')
        
        # ❌ DEPRECATED: Documents NOT synced to local DB
        # Documents are fetched from Auth-Service in real-time only
        
        db.session.commit()
        print(f"✅ Successfully synced user data for {user.login}")
        print(f"   Last name: {last_name}")
        print(f"   First name: {first_name}")
        print(f"   Middle name: {middle_name}")
        print(f"   Suffix: {suffix}")
        print(f"   ➡️ FULL NAME (constructed): {user_data.full_name}")
        print(f"   Phone: {user_data.phone}")
        print(f"   Email: {user_data.e_mail}")
        print(f"   📄 Documents: NOT synced (fetch from Auth-Service API)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error syncing user data from auth-service: {e}")
        db.session.rollback()
        return False


def get_call_center_users_from_auth():
    """
    Получает список пользователей с разрешением на получение уведомлений о новых рефералах из auth-service.
    
    Returns:
        list: Список пользователей с email и другими данными, или пустой список при ошибке
    """
    from flask import current_app
    import requests
    
    try:
        auth_client = getattr(current_app, 'auth_client', None)
        
        if not auth_client:
            print("❌ AuthClient not available")
            return []
        
        # Запрашиваем пользователей с разрешением referal.notifications.new_referral
        users_url = f"/api/services/referal/users-by-permission/referal.notifications.new_referral"
        full_url = f"{auth_client.auth_service_url.rstrip('/')}{users_url}"
        
        print(f"📡 Fetching notification recipients from: {full_url}")
        
        response = requests.get(full_url, headers=_get_api_headers(), timeout=5)
        
        if response.status_code == 200:
            users = response.json()
            print(f"✅ Found {len(users)} users with notification permission")
            return users
        else:
            print(f"⚠️ Failed to get notification recipients: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        print(f"❌ Error getting notification recipients from auth-service: {e}")
        return []