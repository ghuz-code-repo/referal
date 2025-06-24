"""Утилиты для приложения - только необходимые функции"""

import base64
from datetime import datetime
import threading
import time
import os
import re
import smtplib
from typing import List, Optional, Tuple

from flask import current_app, logging
import requests

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


def _send_email_sync(recipient_email, subject, body):
    """
    Внутренняя функция для синхронной отправки email сообщения.
    Предназначена для вызова из send_email_async.
    """
    from email.mime.text import MIMEText
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = os.getenv('SEND_FROM_EMAIL') 
    msg['To'] = recipient_email

    try:
        with smtplib.SMTP(os.getenv('EMAIL_SERVER'), os.getenv('EMAIL_SERVER_PORT')) as server:
            server.starttls()
            server.login(os.getenv('SEND_FROM_EMAIL') , os.getenv('SEND_FROM_EMAIL_PASSWORD'))
            server.sendmail(os.getenv('SEND_FROM_EMAIL'), recipient_email, msg.as_string())
            print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {e}")
        # Убрана рекурсивная попытка, т.к. это плохая практика в асинхронных задачах
        # и может привести к бесконечному циклу.
        # Вместо этого можно добавить более умную логику повторных попыток
        # с задержками, если это необходимо.
        # print(f"Retrying email send in 10 seconds...")
        # time.sleep(10)
        # _send_email_sync(recipient_email, subject, body) # Это может быть бесконечная рекурсия
        # Также можно использовать current_app.logger.error, если контекст доступен
        
def send_email(recipient_email, subject, body):
    """
    Запускает отправку email в отдельном потоке.
    """
    thread = threading.Thread(target=run_async_task, args=(_send_email_sync, recipient_email, subject, body))
    thread.daemon = True # Позволяет программе завершиться, даже если поток еще работает
    thread.start()