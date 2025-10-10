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
        self.base_url = base_url or os.getenv('NOTIFICATION_SERVICE_URL', 'http://notification-service:8082')
        self.base_url = self.base_url.rstrip('/')
        self.timeout = int(os.getenv('NOTIFICATION_SERVICE_TIMEOUT', '30'))
        logger.info(f"Notification client initialized with URL: {self.base_url}")
    
    def send_email(self, recipient: str, subject: str, body: str) -> bool:
        """
        Отправка одного email уведомления
        
        Args:
            recipient: Email получателя
            subject: Тема письма
            body: Тело письма
            
        Returns:
            True если отправка успешна, False в случае ошибки
        """
        try:
            notification = {
                "type": "email",
                "recipient": recipient,
                "subject": subject,
                "content": body
            }
            
            url = f"{self.base_url}/api/v1/notifications"
            logger.info(f"Sending email notification to {recipient} via {url}")
            
            response = requests.post(
                url,
                json=notification,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 202:  # HTTP 202 Accepted
                logger.info(f"Email notification successfully queued for {recipient}")
                return True
            else:
                logger.error(
                    f"Failed to send email notification. Status: {response.status_code}, "
                    f"Response: {response.text}"
                )
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending email notification to {recipient}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email notification: {e}")
            return False
    
    def send_batch_emails(self, notifications: list, batch_id: Optional[str] = None) -> bool:
        """
        Отправка пакета email уведомлений
        
        Args:
            notifications: Список словарей с ключами 'recipient', 'subject', 'body'
            batch_id: Опциональный идентификатор пакета
            
        Returns:
            True если отправка успешна, False в случае ошибки
        """
        try:
            batch_notifications = []
            for notif in notifications:
                batch_notifications.append({
                    "type": "email",
                    "recipient": notif['recipient'],
                    "subject": notif.get('subject', ''),
                    "content": notif['body']
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
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 202:  # HTTP 202 Accepted
                logger.info(f"Batch email notifications successfully queued")
                return True
            else:
                logger.error(
                    f"Failed to send batch email notifications. Status: {response.status_code}, "
                    f"Response: {response.text}"
                )
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
