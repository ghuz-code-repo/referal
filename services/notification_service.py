"""Сервис для уведомлений и создания задач"""

from datetime import datetime, timedelta, timezone
import logging
import random
import requests
import os
from models import Manager


def create_macro_task(full_name, phone_number):
    """Создает новую задачу в MacroTask."""
    # Выбор случайного менеджера
    manager_ids = [manager.macro_id for manager in Manager.query.all()]

    if not manager_ids:
        logging.error("No managers found in the database.")
        return

    random_manager_macro_id = random.choice(manager_ids)

    # Расчет времени для завтрашней задачи
    now_utc = datetime.now(timezone.utc)
    tomorrow_utc_base = now_utc + timedelta(days=1)
    try:
        target_hour = int(os.getenv('MACRO_TASK_HOUR', '15'))
    except (ValueError, TypeError):
        logging.warning("MACRO_TASK_HOUR env variable is invalid, defaulting to 15.")
        target_hour = 15

    tomorrow_dt_utc = tomorrow_utc_base.replace(
        hour=target_hour,
        minute=0,
        second=0,
        microsecond=0
    )

    tomorrow_str = tomorrow_dt_utc.strftime('%Y-%m-%dT%H:%M:%SZ')

    # Получение данных аутентификации
    jwt_token = os.getenv('MACRO_JWT_TOKEN')
    if not jwt_token:
        logging.error("MACRO_JWT_TOKEN environment variable not set.")
        return

    app_id = os.getenv('MACRO_APP_ID')
    if not app_id:
        logging.error("MACRO_APP_ID environment variable not set.")
        return

    macro_task_api_url = os.getenv('MACRO_TASK_API_URL')+'/tasks/create'

    task_data = {
        "manager_id": random_manager_macro_id,
        "title": "Встреча в офисе",
        "description": "Встреча в офисе",
        "date_finish": tomorrow_str,
        "type": "meeting",
    }
    logging.info(f"Sending task data to MacroCRM: {task_data}")

    request_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {jwt_token}",
        "AppId": app_id
    }
    
    try:
        response = requests.post(
            macro_task_api_url,
            json=task_data,
            headers=request_headers
        )
        logging.info(f"MacroCRM Response Status: {response.status_code}")
        logging.info(f"MacroCRM Response Body: {response.text}")
        response.raise_for_status()
        logging.info(f"Task created successfully in external system via MacroCRM API")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to create task in external system via MacroCRM API: {e}")
        if hasattr(e, 'response') and e.response is not None:
             logging.error(f"MacroCRM Response status: {e.response.status_code}")
             logging.error(f"MacroCRM Response body: {e.response.text}")
    try:
        response = requests.post(
            macro_task_api_url,
            json=task_data,
            headers=request_headers
        )
        logging.info(f"MacroCRM Response Status: {response.status_code}")
        logging.info(f"MacroCRM Response Body: {response.text}")
        response.raise_for_status()
        logging.info(f"Task created successfully in external system via MacroCRM API")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to create task in external system via MacroCRM API: {e}")
        if hasattr(e, 'response') and e.response is not None:
             logging.error(f"MacroCRM Response status: {e.response.status_code}")
             logging.error(f"MacroCRM Response body: {e.response.text}")
