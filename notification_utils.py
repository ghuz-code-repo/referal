"""
Утилиты для работы с уведомлениями в referal service
Централизованная логика для определения получателей уведомлений
"""

import os
import requests
import logging

logger = logging.getLogger(__name__)


# Маппинг статусов на разрешения для уведомлений
STATUS_NOTIFICATION_PERMISSIONS = {
    0: "referal.notifications.status.pending",
    1: "referal.notifications.status.analytics_review",
    10: "referal.notifications.status.callcenter_review",
    20: "referal.notifications.status.director_review",
    200: "referal.notifications.status.accepted",
    300: "referal.notifications.status.paid",
    500: "referal.notifications.status.rejected",
}

# Названия статусов для читаемости
STATUS_NAMES = {
    0: "Ждёт проверки",
    1: "Проверка отделом аналитики",
    10: "Проверка колл центром",
    20: "Проверка Коммерческим Директором",
    200: "Акцептовано к оплате",
    300: "Оплачено",
    500: "Отказано",
}


def get_users_with_permission(permission_name):
    """
    Получить список пользователей с определённым разрешением из auth-service
    
    Args:
        permission_name (str): Название разрешения (например, 'referal.notifications.status.callcenter_review')
        
    Returns:
        list: Список пользователей с email и другими данными
    """
    try:
        auth_service_url = os.getenv('AUTH_SERVICE_URL', 'http://auth-service:80')
        users_url = f"{auth_service_url}/api/services/referal/users-by-permission/{permission_name}"
        
        logger.info(f"📡 Fetching users with permission '{permission_name}' from: {users_url}")
        
        response = requests.get(users_url, timeout=5)
        
        if response.status_code == 200:
            users = response.json()
            logger.info(f"✅ Found {len(users)} users with permission '{permission_name}'")
            return users
        else:
            logger.warning(f"⚠️ Failed to fetch users with permission '{permission_name}': {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"❌ Error fetching users with permission '{permission_name}': {str(e)}")
        return []


def get_notification_recipients_for_status(status_id):
    """
    Получить получателей уведомлений для конкретного статуса
    
    Логика:
    1. Получаем пользователей с разрешением для конкретного статуса
    2. Добавляем пользователей с глобальным разрешением referal.notifications.all
    3. Убираем дубликаты по email
    
    Args:
        status_id (int): ID статуса
        
    Returns:
        list: Список уникальных получателей с email
    """
    recipients = []
    seen_emails = set()
    
    # 1. Получаем пользователей с разрешением для конкретного статуса
    if status_id in STATUS_NOTIFICATION_PERMISSIONS:
        status_permission = STATUS_NOTIFICATION_PERMISSIONS[status_id]
        status_users = get_users_with_permission(status_permission)
        
        for user in status_users:
            email = user.get('email')
            if email and email not in seen_emails:
                recipients.append(user)
                seen_emails.add(email)
    
    # 2. Получаем пользователей с глобальным разрешением на все уведомления
    global_users = get_users_with_permission('referal.notifications.all')
    
    for user in global_users:
        email = user.get('email')
        if email and email not in seen_emails:
            recipients.append(user)
            seen_emails.add(email)
    
    logger.info(f"📬 Total {len(recipients)} unique recipients for status {status_id} ({STATUS_NAMES.get(status_id, 'Unknown')})")
    
    return recipients


def get_notification_recipients_for_new_referral():
    """
    Получить получателей уведомлений о создании нового реферала
    
    Логика:
    1. Получаем пользователей с разрешением referal.notifications.new_referral
    2. Добавляем пользователей с глобальным разрешением referal.notifications.all
    3. Убираем дубликаты по email
    
    Returns:
        list: Список уникальных получателей с email
    """
    recipients = []
    seen_emails = set()
    
    # 1. Получаем пользователей с разрешением на уведомления о новых рефералах
    new_referral_users = get_users_with_permission('referal.notifications.new_referral')
    
    for user in new_referral_users:
        email = user.get('email')
        if email and email not in seen_emails:
            recipients.append(user)
            seen_emails.add(email)
    
    # 2. Получаем пользователей с глобальным разрешением на все уведомления
    global_users = get_users_with_permission('referal.notifications.all')
    
    for user in global_users:
        email = user.get('email')
        if email and email not in seen_emails:
            recipients.append(user)
            seen_emails.add(email)
    
    logger.info(f"📬 Total {len(recipients)} unique recipients for new referral notification")
    
    return recipients


def get_status_display_name(status_id):
    """Получить читаемое название статуса"""
    return STATUS_NAMES.get(status_id, f"Статус {status_id}")
