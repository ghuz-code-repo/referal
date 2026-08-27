"""
Клиент для работы с Notification Service
Обеспечивает отправку email уведомлений через централизованный сервис
"""

import os
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class NotificationClient:
    """Клиент для отправки уведомлений через Notification Service"""
    
    def __init__(self, base_url: Optional[str] = None):
        """
        Инициализация клиента
        
        Args:
            base_url: URL notification service. Если не указан, берется из переменной окружения
        """
        self.base_url = base_url or os.getenv('NOTIFICATION_SERVICE_URL', 'http://notification-service:80')
        self.base_url = self.base_url.rstrip('/')
        self.timeout = int(os.getenv('NOTIFICATION_SERVICE_TIMEOUT', '30'))
        # Персональный ключ сервиса для аутентификации в notification-service
        self.api_key = os.getenv('NOTIFICATION_API_KEY') or os.getenv('INTERNAL_API_KEY', '')
        logger.info(f"Notification client initialized with URL: {self.base_url}")

    def _headers(self) -> dict:
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['X-API-Key'] = self.api_key
        return headers
    
    @staticmethod
    def _recipient_fields(login: Optional[str] = None,
                          external_recipient: Optional[str] = None) -> dict:
        """
        Собрать поля адресации для notification-service.

        Получателя-сотрудника адресуем логином портала: адрес доставки (email, chat_id)
        определяет auth-service, сервису его знать не нужно. Внешним получателям —
        external_recipient. Заполнено должно быть ровно одно поле.

        Args:
            login: логин пользователя портала
            external_recipient: адрес получателя вне портала

        Returns:
            dict с одним ключом адресации
        """
        if sum(1 for v in (login, external_recipient) if v) != 1:
            raise ValueError(
                "Нужно ровно одно поле получателя: login или external_recipient"
            )
        if login:
            return {"login": login}
        return {"external_recipient": external_recipient}

    def send_email(self, subject: str, body: str,
                   login: Optional[str] = None,
                   external_recipient: Optional[str] = None) -> bool:
        """
        Отправка одного email уведомления
        
        Args:
            subject: Тема письма
            body: Тело письма
            login: Логин пользователя портала (предпочтительно)
            external_recipient: Email получателя вне портала
            
        Returns:
            True если отправка успешна, False в случае ошибки
        """
        try:
            addressing = self._recipient_fields(login, external_recipient)
            target = login or external_recipient

            notification = {
                "type": "email",
                "subject": subject,
                "content": body,
                **addressing,
            }
            
            url = f"{self.base_url}/api/v1/notifications"
            logger.info(f"Sending email notification to {target} via {url}")
            
            response = requests.post(
                url,
                json=notification,
                timeout=self.timeout,
                headers=self._headers()
            )
            
            if response.status_code == 202:  # HTTP 202 Accepted
                logger.info(f"Email notification successfully queued for {target}")
                return True

            # 400 — получателя не удалось разрешить (нет такого логина, нет email,
            # нет доступа к сервису); 503 — auth-service недоступен, можно повторить
            logger.error(
                f"Failed to send email notification. Status: {response.status_code}, "
                f"Response: {response.text}"
            )
            return False
                
        except ValueError as e:
            logger.error(f"Некорректная адресация уведомления: {e}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending email notification to {target}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email notification: {e}")
            return False
    
    def send_batch_emails(self, notifications: list, batch_id: Optional[str] = None) -> bool:
        """
        Отправка пакета email уведомлений
        
        Args:
            notifications: Список словарей с ключами 'subject', 'body' и одним полем
                адресации: 'login' (пользователь портала) либо 'external_recipient'
                (получатель вне портала)
            batch_id: Опциональный идентификатор пакета
            
        Returns:
            True если отправка успешна, False в случае ошибки
        """
        try:
            batch_notifications = []
            for notif in notifications:
                addressing = self._recipient_fields(
                    notif.get('login'),
                    notif.get('external_recipient'),
                )
                batch_notifications.append({
                    "type": "email",
                    "subject": notif.get('subject', ''),
                    "content": notif['body'],
                    **addressing,
                })
            
            payload = {
                "notifications": batch_notifications
            }
            
            if batch_id:
                payload["batch_id"] = batch_id
            
            url = f"{self.base_url}/api/v1/notifications/batch"
            logger.info(f"Sending batch of {len(batch_notifications)} email notifications via {url}")
            
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout,
                headers=self._headers()
            )
            
            if response.status_code == 202:  # HTTP 202 Accepted
                # Отказ по отдельному получателю не рушит пачку: такие уведомления
                # приходят списком unresolved и создаются сразу со статусом failed
                try:
                    unresolved = (response.json() or {}).get('unresolved') or []
                except ValueError:  # тело не JSON — не повод считать пачку упавшей
                    unresolved = []
                if unresolved:
                    logger.warning(
                        f"Batch queued, но {len(unresolved)} получателей не разрешены: {unresolved}"
                    )
                else:
                    logger.info("Batch email notifications successfully queued")
                return True

            logger.error(
                f"Failed to send batch email notifications. Status: {response.status_code}, "
                f"Response: {response.text}"
            )
            return False
                
        except ValueError as e:
            logger.error(f"Некорректная адресация в пачке уведомлений: {e}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending batch email notifications: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending batch email notifications: {e}")
            return False
    
    def check_health(self) -> bool:
        """
        Проверка доступности notification service
        
        Returns:
            True если сервис доступен, False в противном случае
        """
        try:
            url = f"{self.base_url}/api/v1/health"
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except:
            return False


# Глобальный экземпляр клиента
_notification_client: Optional[NotificationClient] = None


def get_notification_client() -> NotificationClient:
    """
    Получить глобальный экземпляр клиента notification service
    
    Returns:
        Экземпляр NotificationClient
    """
    global _notification_client
    if _notification_client is None:
        _notification_client = NotificationClient()
    return _notification_client


def init_notification_client(base_url: Optional[str] = None) -> NotificationClient:
    """
    Инициализация глобального клиента notification service
    
    Args:
        base_url: URL notification service
        
    Returns:
        Экземпляр NotificationClient
    """
    global _notification_client
    _notification_client = NotificationClient(base_url)
    return _notification_client
