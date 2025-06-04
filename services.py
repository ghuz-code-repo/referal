# Импорты необходимых модулей и классов
from datetime import timedelta, timezone

import pandas as pd
from models import *
import logging
import random
import requests
import utils
import os
import pymysql
# from flask_login import login_required
from pymysql import MySQLError
from models import db, MacroContact, MacroDeal
from datetime import datetime, timedelta
import re
from sqlalchemy.exc import IntegrityError
from flask import flash, redirect, url_for, request
from werkzeug.security import generate_password_hash

# Функция для обновления информации о сделке и баланса пользователя
def update_deal_and_balance(referral, user=None):
    """Обновляет информацию о сделке и баланс пользователя на основе данных реферала.

    Аргументы:
        referral (Referral): Объект реферала, для которого нужно обновить информацию.
        user (User, optional): Объект пользователя, если не указан, используется referral.user.

    Возвращает:
        None
    """
    # Поиск контакта, связанного с рефералом, по номеру телефона
    contact = MacroContact.query.filter_by(phone_number=referral.phone_number).first()
    
    # Use the provided user or get from referral
    current_user = user or referral.user

    # Если контакт найден
    if contact:
        logging.debug(f"Found contact: {contact.contacts_id} for referral: {referral.id}")
        # Обновление contact_id у реферала
        referral.contact_id = contact.contacts_id
        # Поиск сделки, связанной с контактом
        deals = MacroDeal.query.filter_by(contacts_buy_id=contact.contacts_id).all()
        if not deals:
            logging.debug(f"No deals found for referral: {referral.id}")
            return 
        
        real_deal = MacroDeal()
        for deal in deals:
            if deal.deal_status_name == "Сделка проведена" or deal.deal_status_name == "Сделка в работе":
                real_deal = deal
                break

        if real_deal:
            logging.debug(f"Found deal: {real_deal.id} with status: {real_deal.deal_status_name} for contact: {contact.id}")
            # Обновление номера контракта и площади сделки у реферала
            referral.contract_number = real_deal.agreement_number
            referral.deal_metr = real_deal.deal_metr

            # Если баланс еще не был обновлен для этой сделки
            if not referral.balance_updated:
                # Обновление баланса пользователя в зависимости от площади сделки
                if 20.0 <= referral.deal_metr < 40.0:
                    referral.withdrawal_amount = int(os.getenv('REFERAL_WITHDRAWAL_FOR_40M'))
                elif 40.0 <= referral.deal_metr < 60.0:
                    referral.withdrawal_amount = int(os.getenv('REFERAL_WITHDRAWAL_FOR_60M'))
                elif 60.0 <= referral.deal_metr < 80.0:
                    referral.withdrawal_amount = int(os.getenv('REFERAL_WITHDRAWAL_FOR_80M'))
                elif referral.deal_metr >= 80.0:
                    referral.withdrawal_amount = int(os.getenv('REFERAL_WITHDRAWAL_FOR_81'))
                # Установка флага, что баланс обновлен
                referral.balance_updated = True
                current_user.current_balance += referral.withdrawal_amount
                logging.debug(f"User balance updated: {current_user.current_balance}")
        else:
            logging.debug(f"No deal found for contact: {contact.id}")
    else:
        logging.debug(f"No contact found for referral: {referral.id}")

# Функция для создания нового реферала
def create_new_referral(full_name, phone_number, user):
    """Создает новый объект реферала.

    Аргументы:
        full_name (str): Полное имя реферала.
        phone_number (str): Номер телефона реферала.
        user (User): Пользователь, создающий реферала.

    Возвращает:
        Referral или None: Объект нового реферала, если он успешно создан и не существует,
                         в противном случае возвращает None.

    Описание:
        Эта функция создает новый объект реферала, проверяя, не существует ли уже реферал с таким же именем
        или номером телефона. Если реферал не существует, функция создает новый объект Referral, связывает его
        с контактом из таблицы MacroContact (если такой контакт существует) и возвращает этот объект.
        В противном случае (если реферал уже существует) функция возвращает None.
    """
    # User validation - make sure user is not None and has an id
    if not user:
        print("ERROR: Cannot create referral - user is None")
        return None
    
    if not hasattr(user, 'id') or not user.id:
        print(f"ERROR: User has no valid ID: {user}")
        return None

    # Проверка на существование реферала с таким же именем или номером телефона
    existing_referral = Referral.query.filter(
        (Referral.full_name == full_name) | (Referral.phone_number == phone_number)
    ).first()

    if existing_referral:
        return None

    # Поиск контакта по номеру телефона
    contact = MacroContact.query.filter_by(phone_number=phone_number).first()
    # Получение ID контакта или None, если контакт не найден
    contact_id = contact.contacts_id if contact else None

    # Создание нового объекта реферала
    new_referral = Referral(
        full_name=full_name,
        phone_number=phone_number,
        contact_id=contact_id,
        user_id=user.id  # Использование переданного пользователя вместо current_user
    )
    # Print debug info
    print(f"Creating referral with user_id = {user.id}")
    
    # Возвращение созданного объекта реферала
    return new_referral
# Функция для обновления информации о сделках пользователя
def update_deal_info(user):
    """Обновляет информацию о сделках для всех рефералов пользователя и корректирует баланс.

    Аргументы:
        user (User): Объект пользователя, для которого нужно обновить информацию.

    Возвращает:
        None
    """
    # Получение ID пользователя
    user_id = user.id
    # Получение списка всех рефералов пользователя
    referrals = Referral.query.filter_by(user_id=user_id).all()

    # Для каждого реферала
    for referral in referrals:
        # Обновление информации о сделке и баланса
        update_deal_and_balance(referral)

    # Сохранение изменений в базе данных
    db.session.commit()
    logging.debug(f"Final user balance: {user.current_balance}")

def create_macro_task(full_name, phone_number):
    """Создает новую задачу в MacroTask.

    Аргументы:
        full_name (str): Полное имя реферала.
        phone_number (str): Номер телефона реферала.

    Возвращает:
        None

    Исключения:
        Может вызвать исключение при ошибке создания задачи.
    """

    # Выбор случайного менеджера из списка
    manager_ids = [manager.macro_id for manager in Manager.query.all()] # List comprehension

    if not manager_ids:
        logging.error("No managers found in the database.")
        return

    random_manager_macro_id = random.choice(manager_ids) # Use random.choice

    # Calculate tomorrow's date at the specified hour in UTC
    now_utc = datetime.now(timezone.utc)
    # Calculate tomorrow relative to UTC now
    tomorrow_utc_base = now_utc + timedelta(days=1)
    try:
        target_hour = int(os.getenv('MACRO_TASK_HOUR', '15')) # Default to 15 if not set
    except (ValueError, TypeError):
        logging.warning("MACRO_TASK_HOUR env variable is invalid, defaulting to 15.")
        target_hour = 15 # Default hour if env var is invalid

    tomorrow_dt_utc = tomorrow_utc_base.replace(
        hour=target_hour,
        minute=0,
        second=0,
        microsecond=0
    )

    # Format as YYYY-MM-DDTHH:MM:SSZ (ISO 8601 UTC)
    tomorrow_str = tomorrow_dt_utc.strftime('%Y-%m-%dT%H:%M:%SZ')


    # 1. Get the Bearer Token (JWT) - Replace with your actual token source
    jwt_token = os.getenv('MACRO_JWT_TOKEN')
    if not jwt_token:
        logging.error("MACRO_JWT_TOKEN environment variable not set.")
        # Handle the error appropriately - maybe return or raise an exception
        return

    # 2. Get the App ID - Replace with your actual App ID source
    app_id = os.getenv('MACRO_APP_ID')
    if not app_id:
        logging.error("MACRO_APP_ID environment variable not set.")
        # Handle the error appropriately
        return
    # --- End Authentication Details ---

    creds = {
        "domain": os.getenv('MACRO_DOMAIN'), # Get from env or use default
        "time": str(int(datetime.now().timestamp())), # Convert timestamp to string integer
        "secret": os.getenv('MACRO_SECRET') # Get from env or use default
    }

    # Construct the string to hash
    # hash_string = f"{creds['domain']}{creds['time']}{creds['secret']}"
    # Calculate MD5 hash
    # token = hashlib.md5(hash_string.encode('utf-8')).hexdigest() # Encode string before hashing

    macro_task_api_url = os.getenv('MACRO_TASK_API_URL')+'/tasks/create' # Get from env or use default

    task_data = {
        "manager_id": random_manager_macro_id,
        "title": "Встреча в офисе",
        "description": "Встреча в офисе",
        "date_finish": tomorrow_str,
        "type": "meeting",
    }
    logging.info(f"Sending task data to MacroCRM: {task_data}") # Log the data


    request_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {jwt_token}", # Add Bearer token
        "AppId": app_id                       # Add AppId header
    }
    # Send POST request to create task in external system
    try:
        response = requests.post(
            macro_task_api_url,
            json=task_data,
            headers=request_headers
        )
        logging.info(f"MacroCRM Response Status: {response.status_code}")
        logging.info(f"MacroCRM Response Body: {response.text}")
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        logging.info(f"Task created successfully in external system via MacroCRM API")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to create task in external system via MacroCRM API: {e}")
        if hasattr(e, 'response') and e.response is not None:
             logging.error(f"MacroCRM Response status: {e.response.status_code}")
             logging.error(f"MacroCRM Response body: {e.response.text}")
        # Consider how to handle this error (e.g., notify admin, retry later)

def request_withdrawal(referral_id, user):
    """
    Обрабатывает запрос на вывод средств от пользователя, отправляет уведомление по email и обновляет статус вывода.
    """
    user_full_name = user.full_name
    referral = Referral.query.filter_by(id=referral_id).first()

    if not referral.balance_pending_withdrawal and referral.withdrawal_amount > 0:
        user.pending_withdrawal += referral.withdrawal_amount
        user.current_balance -= referral.withdrawal_amount
        referral.status_id = 1
        referral.status_name = Status.query.filter_by(id=1).first().name
        referral.balance_pending_withdrawal = True
        db.session.commit()
        # send_withdrawal_email(user_full_name, referral.withdrawal_amount, referral.full_name)
        recipient_email = os.getenv('MAIN_ADMIN_EMAIL')
        subject = "Запрос на вывод средств"
        body = f"Сотрудник {user_full_name} сделал запрос на вывод средств в размере {referral.withdrawal_amount} за счет реферала {referral.full_name}"
        return utils.send_email(recipient_email, subject, body)

def fetch_data_from_mysql():
    try:
        connection = pymysql.connect(
            host=os.getenv('MYSQL_HOST'),
            port=int(os.getenv('MYSQL_PORT')),
            database=os.getenv('MYSQL_DATABASE'),
            user=os.getenv('MYSQL_USER'),
            password=os.getenv('MYSQL_PASSWORD')
        )
        print("Connected to MySQL database successfully")
        with connection.cursor() as cursor:
            date_threshold = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
            query_contacts = """
                       SELECT id, contacts_buy_name, contacts_buy_phones
                       FROM estate_deals_contacts
                       WHERE date_modified >= %s
                   """
            cursor.execute(query_contacts, (date_threshold,))
            print(f"Executing query: {query_contacts} with date_threshold: {date_threshold}")   
            total_records = cursor.rowcount
            loaded_records = 0

            batch_size = 1000
            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break

                with db.session.no_autoflush:
                    for row in rows:
                        contact_id, full_name, phone_number = row
                        formatted_phone_number = utils.format_phone_number(phone_number)
                        if not formatted_phone_number:
                            continue
                        # First check by contacts_id
                        existing_contact = MacroContact.query.filter_by(
                            contacts_id=contact_id
                        ).first()
                        if existing_contact:
                            # Update existing contact
                            existing_contact.full_name = full_name
                            existing_contact.phone_number = formatted_phone_number
                        else:

                            # Check if phone number exists
                            phone_exists = MacroContact.query.filter_by(
                                phone_number=formatted_phone_number
                            ).first()
                            if phone_exists:
                                # Update the existing record with this phone
                                phone_exists.contacts_id = contact_id
                                phone_exists.full_name = full_name
                            else:
                                # Create new contact
                                new_contact = MacroContact(
                                    contacts_id=contact_id,
                                    full_name=full_name,
                                    phone_number=formatted_phone_number
                                )
                                db.session.add(new_contact)
                        loaded_records += 1
                        try:
                            db.session.commit()
                        except IntegrityError:
                            db.session.rollback()
                            print(f"Error processing record: {contact_id}, {formatted_phone_number}")
                            continue
                    print(f"Loaded {loaded_records} of {total_records} records") 
                    
            # Fetch data from estate_deals table
            query_deals = """
                SELECT deal_status_name, agreement_number, contacts_buy_id, deal_area
                FROM estate_deals
            """
            cursor.execute(query_deals)

            total_deals = cursor.rowcount
            loaded_deals = 0

            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break


                for row in rows:
                    deal_status_name, agreement_number, contacts_buy_id, deal_area = row
                    new_deal = MacroDeal(
                        deal_status_name=deal_status_name,
                        agreement_number=agreement_number,
                        contacts_buy_id=contacts_buy_id,
                        deal_metr=deal_area  # Map deal_area to deal_metr
                    )
                    db.session.add(new_deal)
                    loaded_deals += 1
                print(f"Loaded {loaded_deals} of {total_deals} deals")
                db.session.commit()

            # Check if the record with id 4272995 was added

                contact = MacroContact.query.filter_by(id=4272995).first()
                if contact:
                    print(f"Record with ID 4272995 found: {contact.full_name}")
                else:
                    print("Record with ID 4272995 not found.")
        print("Data fetch and update completed successfully")
    except MySQLError as e:
        print(f"Error: {e}")
    finally:
        connection.close()
        print("Database connection closed")
        