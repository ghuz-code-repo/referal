# Импорты необходимых модулей и классов
from datetime import datetime, timedelta, timezone
from typing import List # Consolidated datetime imports

from flask import current_app
import pandas as pd
from models import *
import logging
import random
import requests
from referal.old.services import _fetch_and_process_deals_task
import utils
import os
import pymysql
from pymysql import MySQLError
from datetime import datetime

# Функция для обновления информации о сделке и баланса пользователя
def update_deal_and_balance(referal, user):
    """Обновляет информацию о сделке и баланс пользователя на основе данных реферала.
    НЕ перезаписывает вручную введенные данные реферала.
    """
    print(f"DEBUG update_deal_and_balance: ---- Starting for Referal ID: {referal.id}, Phone: {referal.referal_data.phone_number} ----")
    
    # For referals with multiple phone numbers, find the exact matching contact
    referal_phone = referal.referal_data.phone_number
    contact = None
    
    # Форматируем номер телефона для поиска
    formatted_referal_phone = utils.format_phone_number(referal_phone)
    if not formatted_referal_phone:
        formatted_referal_phone = referal_phone
    
    print(f"DEBUG update_deal_and_balance: Searching for contact with formatted phone: {formatted_referal_phone}")
    
    # If the referal has multiple phones (comma-separated), try to find exact match
    if ',' in referal_phone:
        phones = [phone.strip() for phone in referal_phone.split(',')]
        for phone in phones:
            formatted_phone = utils.format_phone_number(phone)
            if not formatted_phone:
                formatted_phone = phone
            contact = MacroContact.query.filter_by(phone_number=formatted_phone).first()
            if contact:
                print(f"DEBUG update_deal_and_balance: Found exact match for phone: {formatted_phone}")
                # Update referal to use the matched phone number for processing
                referal.referal_data.phone_number = formatted_phone
                break
    else:
        # Single phone number - direct lookup with formatted phone
        contact = MacroContact.query.filter_by(phone_number=formatted_referal_phone).first()
    
    current_user = user

    if contact:
        print(f"DEBUG update_deal_and_balance: Found MacroContact - Local DB ID: {contact.id}, contacts_id (from source): {contact.contacts_id}, Name: {contact.full_name}, Phone: {contact.phone_number}")
        
        # УБРАНО: НЕ обновляем имя реферала из MacroContact, сохраняем вручную введенные данные
        # Update Referal's own data from the found MacroContact
        # if referal.referal_data.full_name != contact.full_name:
        #     print(f"DEBUG update_deal_and_balance: Updating referal.referal_data.full_name from '{referal.referal_data.full_name}' to '{contact.full_name}'")
        #     referal.referal_data.full_name = contact.full_name
        
        print(f"DEBUG update_deal_and_balance: Keeping manual referal name: '{referal.referal_data.full_name}' (MacroContact has: '{contact.full_name}')")

        referal.contact_id = contact.contacts_id 
        
        print(f"DEBUG update_deal_and_balance: Searching for MacroDeal(s) with contacts_buy_id = {contact.contacts_id}")
        deals = MacroDeal.query.filter_by(contacts_buy_id=contact.contacts_id).all()
        
        if not deals:
            print(f"DEBUG update_deal_and_balance: No MacroDeals found in local DB for contacts_buy_id: {contact.contacts_id}")
            return 
        
        print(f"DEBUG update_deal_and_balance: Found {len(deals)} MacroDeal(s) for contacts_buy_id: {contact.contacts_id}. Iterating to check status...")
        
        suitable_deal_found = False
        for deal_obj in deals:
            print(f"DEBUG update_deal_and_balance: Checking Deal - Local DB ID: {deal_obj.id}, Agreement No: '{deal_obj.agreement_number}', Status: '{deal_obj.deal_status_name}', contacts_buy_id: {deal_obj.contacts_buy_id}")
            if deal_obj.deal_status_name == "Сделка проведена": # or deal_obj.deal_status_name == "Сделка в работе":
                print(f"DEBUG update_deal_and_balance: MATCH! Suitable deal found: Agreement No: '{deal_obj.agreement_number}', Status: '{deal_obj.deal_status_name}'")
                if deal_obj not in referal.deals:
                    referal.deals.append(deal_obj)
                
                referal.referal_data.contract_number = deal_obj.agreement_number
                referal.deal_metr = deal_obj.deal_metr
                print(f"DEBUG update_deal_and_balance: Set referal_data.contract_number to '{deal_obj.agreement_number}' and deal_metr to {deal_obj.deal_metr}")
                suitable_deal_found = True
                break

        if not suitable_deal_found:
            print(f"DEBUG update_deal_and_balance: No deals with status 'Сделка проведена' found for contacts_buy_id: {contact.contacts_id}")
        
        # The balance update logic depends on referal.deal_metr being set.
        if suitable_deal_found and not referal.balance_updated:
            print(f"DEBUG update_deal_and_balance: Proceeding to update balance. Current withdrawal_amount: {referal.withdrawal_amount}, deal_metr: {referal.deal_metr}")
            # Обновление баланса пользователя в зависимости от площади сделки
            if 20.0 <= referal.deal_metr < 40.0:
                referal.withdrawal_amount = int(os.getenv('REFERAL_WITHDRAWAL_FOR_40M', 0))
            elif 40.0 <= referal.deal_metr < 60.0:
                referal.withdrawal_amount = int(os.getenv('REFERAL_WITHDRAWAL_FOR_60M', 0))
            elif 60.0 <= referal.deal_metr < 80.0:
                referal.withdrawal_amount = int(os.getenv('REFERAL_WITHDRAWAL_FOR_80M', 0))
            elif referal.deal_metr >= 80.0:
                referal.withdrawal_amount = int(os.getenv('REFERAL_WITHDRAWAL_FOR_81M', 0))
            
            if referal.withdrawal_amount > 0:
                referal.balance_updated = True
                current_user.current_balance += referal.withdrawal_amount
                print(f"DEBUG update_deal_and_balance: Updated user balance by {referal.withdrawal_amount}. New balance: {current_user.current_balance}")
            else:
                print(f"DEBUG update_deal_and_balance: No withdrawal amount set for deal_metr: {referal.deal_metr}")
                
        elif suitable_deal_found and referal.balance_updated:
            print(f"DEBUG update_deal_and_balance: Deal found but balance already updated for this referal")

    else:
        print(f"DEBUG update_deal_and_balance: No MacroContact found for formatted phone: {formatted_referal_phone}")
    
    print(f"DEBUG update_deal_and_balance: ---- Finished for Referal ID: {referal.id}. Final contract_number: '{referal.referal_data.contract_number}' ----")

# Функция для создания нового реферала
def create_new_referal(full_name, phone_number, user):
    """Создает новый объект реферала.

    Аргументы:
        full_name (str): Полное имя реферала.
        phone_number (str): Номер телефона реферала.
        user (User): Пользователь, создающий реферала.

    Возвращает:
        Referal или None: Объект нового реферала, если он успешно создан и не существует,
                         в противном случае возвращает None.

    Описание:
        Эта функция создает новый объект реферала, проверяя, не существует ли уже реферал с таким же именем
        или номером телефона. Если реферал не существует, функция создает новый объект Referal, связывает его
        с контактом из таблицы MacroContact (если такой контакт существует) и возвращает этот объект.
        В противном случае (если реферал уже существует) функция возвращает None.
    """
    # User validation - make sure user is not None and has an id
    if not user:
        print("ERROR: Cannot create referal - user is None")
        return None
    
    if not hasattr(user, 'id') or not user.id:
        print(f"ERROR: User has no valid ID: {user}")
        return None

    # Форматируем номер телефона для единообразного поиска
    formatted_phone = utils.format_phone_number(phone_number)
    if not formatted_phone:
        print(f"ERROR: Unable to format phone number: {phone_number}")
        formatted_phone = phone_number  # Используем исходный номер если форматирование не удалось

    print(f"DEBUG create_new_referal: Original phone: '{phone_number}', Formatted phone: '{formatted_phone}'")

    # Поиск контакта по отформатированному номеру телефона
    contact = MacroContact.query.filter_by(phone_number=formatted_phone).first()
    # Получение ID контакта или None, если контакт не найден
    contact_id = contact.contacts_id if contact else None
    
    if contact:
        print(f"DEBUG create_new_referal: Found contact with ID {contact.contacts_id} for phone {formatted_phone}")
    else:
        print(f"DEBUG create_new_referal: No contact found for formatted phone {formatted_phone}")

    # Создание нового объекта реферала с отформатированным номером
    new_referal = Referal(
        user_id=user.id,
        contact_id=contact_id,
        referal_data=ReferalData(
            full_name=full_name,
            phone_number=formatted_phone,  # Сохраняем отформатированный номер
        ),
    )
    
    # Print debug info
    print(f"Creating referal with user_id = {user.id}")
    
    # Возвращение созданного объекта реферала
    return new_referal
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
    referals = Referal.query.filter_by(user_id=user_id).all()

    # Для каждого реферала
    for referal in referals:
        # Обновление информации о сделке и баланса
        update_deal_and_balance(referal, user)

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

def request_withdrawal(referal_id, user):
    """
    Обрабатывает запрос на вывод средств от пользователя, отправляет уведомление по email и обновляет статус вывода.
    """
    user_full_name = user.user_data.full_name
    referal = Referal.query.filter_by(id=referal_id).first()
    if not referal.balance_pending_withdrawal and referal.withdrawal_amount > 0:
        user.pending_withdrawal += referal.withdrawal_amount
        user.current_balance -= referal.withdrawal_amount
        referal.status_id = 1
        referal.status_name = Status.query.filter_by(id=1).first().name
        referal.balance_pending_withdrawal = True
        db.session.commit()
        # send_withdrawal_email(user_full_name, referal.withdrawal_amount, referal.full_name)
        recipient_email = os.getenv('MAIN_ADMIN_EMAIL')
        subject = "Запрос на вывод средств по реферальной программе"
        body = f"Сотрудник {user_full_name} сделал запрос на вывод средств в размере {referal.withdrawal_amount} за счет реферала {referal.referal_data.full_name}"
        return utils.send_email(recipient_email, subject, body)

def fetch_data_from_mysql():
    """
    Fetches data for contacts and deals from MySQL synchronously.
    Returns results with status information.
    """
    app = current_app._get_current_object() 

    mysql_config = {
        'host': os.getenv('MYSQL_HOST'),
        'port': int(os.getenv('MYSQL_PORT')),
        'database': os.getenv('MYSQL_DATABASE'),
        'user': os.getenv('MYSQL_USER'),
        'password': os.getenv('MYSQL_PASSWORD'),
        'cursorclass': pymysql.cursors.Cursor  # Use standard cursor
    }
    
    print("=== Starting synchronous data fetch ===")
    print(f"MySQL Config: {mysql_config['host']}:{mysql_config['port']}/{mysql_config['database']}")
    
    # Execute contacts task first
    print("\n=== CONTACTS TASK ===")
    contacts_result = _fetch_and_process_contacts_task(mysql_config, app.app_context())
    print(f"Contacts task result: {contacts_result}")
    
    # Execute deals task second
    print("\n=== DEALS TASK ===")
    deals_result = _fetch_and_process_deals_task(mysql_config, app.app_context())
    print(f"Deals task result: {deals_result}")
    
    # Final verification of both tables
    with app.app_context():
        final_contacts_count = MacroContact.query.count()
        final_deals_count = MacroDeal.query.count()
        print(f"\n=== FINAL VERIFICATION ===")
        print(f"MacroContact table: {final_contacts_count} records")
        print(f"MacroDeal table: {final_deals_count} records")
    
    # Return combined results
    return {
        "status": "success" if contacts_result.get('status') == 'success' and deals_result.get('status') == 'success' else "partial_success",
        "contacts": contacts_result,
        "deals": deals_result,
        "message": f"Data fetching completed. Contacts: {contacts_result.get('loaded', 0)}, Deals: {deals_result.get('loaded', 0)}",
        "final_verification": {
            "contacts_count": final_contacts_count,
            "deals_count": final_deals_count
        }
    }

def prioritize_phone_numbers(phone_numbers: List[str]) -> str:
    """
    Выбирает приоритетный номер телефона из списка:
    1. Приоритет узбекским номерам (+998)
    2. Если только российские (+7), берет первый
    3. Если есть и узбекские и российские, берет узбекский
    """
    if not phone_numbers:
        return None
    
    if len(phone_numbers) == 1:
        return phone_numbers[0]
    
    uzbek_phones = []
    russian_phones = []
    other_phones = []
    
    for phone in phone_numbers:
        formatted_phone = utils.format_phone_number(phone)
        if formatted_phone:
            if formatted_phone.startswith('+998'):
                uzbek_phones.append(formatted_phone)
            elif formatted_phone.startswith('+7'):
                russian_phones.append(formatted_phone)
            else:
                other_phones.append(formatted_phone)
    
    # Приоритет: узбекские -> российские -> другие
    if uzbek_phones:
        return uzbek_phones[0]  # Берем первый узбекский номер
    elif russian_phones:
        return russian_phones[0]  # Берем первый российский номер
    elif other_phones:
        return other_phones[0]  # Берем первый из других номеров
    else:
        # Если ни один номер не удалось отформатировать, возвращаем первый исходный
        return phone_numbers[0]

def sync_referals_with_macro_contacts():
    """
    Синхронизирует существующие рефералы с обновленными MacroContact записями.
    1. Если номер телефона реферала совпадает с MacroContact, обновляет contact_id
    2. Если имена совпадают, но телефоны разные, обновляет телефон реферала с приоритетом узбекских номеров
    """
    print("Starting referals synchronization with MacroContact...")
    
    # Получаем все рефералы
    all_referals = Referal.query.all()
    updated_count = 0
    phone_updated_count = 0
    
    for referal in all_referals:
        if not referal.referal_data:
            continue
            
        referal_phone = referal.referal_data.phone_number
        referal_name = referal.referal_data.full_name
        
        # Приоритет 1: Поиск по точному совпадению телефона
        matching_contact_by_phone = MacroContact.query.filter_by(phone_number=referal_phone).first()
        
        if matching_contact_by_phone:
            # Обновляем contact_id реферала
            old_contact_id = referal.contact_id
            referal.contact_id = matching_contact_by_phone.contacts_id
            
            # Обновляем имя реферала, если оно отличается от MacroContact
            if referal.referal_data.full_name != matching_contact_by_phone.full_name:
                print(f"Updating referal name from '{referal.referal_data.full_name}' to '{matching_contact_by_phone.full_name}' for phone {referal_phone}")
                referal.referal_data.full_name = matching_contact_by_phone.full_name
            
            if old_contact_id != matching_contact_by_phone.contacts_id:
                print(f"Updated referal contact_id from {old_contact_id} to {matching_contact_by_phone.contacts_id} for phone {referal_phone}")
                updated_count += 1
        else:
            # Приоритет 2: Поиск по имени (если телефон не найден)
            if referal_name:
                # Ищем все контакты с таким же именем
                matching_contacts_by_name = MacroContact.query.filter_by(full_name=referal_name).all()
                
                if matching_contacts_by_name:
                    # Собираем все номера телефонов для этого имени
                    available_phones = [contact.phone_number for contact in matching_contacts_by_name]
                    
                    # Выбираем приоритетный номер (узбекский если есть)
                    best_phone = prioritize_phone_numbers(available_phones)
                    
                    if best_phone and best_phone != referal_phone:
                        # Находим контакт с выбранным номером
                        best_contact = next((c for c in matching_contacts_by_name if c.phone_number == best_phone), None)
                        
                        if best_contact:
                            old_phone = referal.referal_data.phone_number
                            referal.referal_data.phone_number = best_contact.phone_number
                            referal.contact_id = best_contact.contacts_id
                            
                            print(f"Updated referal phone from '{old_phone}' to '{best_contact.phone_number}' for name '{referal_name}' (prioritized Uzbek number)")
                            phone_updated_count += 1
                            updated_count += 1
    
    # Сохраняем изменения
    try:
        db.session.commit()
        print(f"Synchronization completed: {updated_count} referals updated, {phone_updated_count} phone numbers updated")
    except Exception as e:
        db.session.rollback()
        print(f"Error during synchronization commit: {e}")
        raise

def _fetch_and_process_contacts_task(mysql_config, app_context):
    """
    Fetches contacts from MySQL and upserts them into the local MacroContact table.
    Handles multiple phone numbers separated by commas as separate contact records.
    After completion, synchronizes existing referals with updated contacts.
    """
    task_name = "Contacts Task"
    loaded_records = 0
    total_records_to_process = 0
    errors = []
    connection = None
    grand_total_skipped_unformattable_phone = 0
    grand_total_skipped_in_batch_conflict = 0
    grand_total_skipped_staging_error = 0
    
    unformattable_phone_details_list = []

    print(f"{task_name}: Starting.")
    with app_context:
        print(f"{task_name}: Inside app context")
        
        # Clear existing contacts for fresh import
        print(f"{task_name}: Clearing existing contacts...")
        try:
            deleted_count = MacroContact.query.count()
            MacroContact.query.delete()
            db.session.commit()
            print(f"{task_name}: Cleared {deleted_count} existing contacts.")
        except Exception as e:
            print(f"{task_name}: Error clearing contacts: {e}")
            db.session.rollback()
        
        print(f"{task_name}: Attempting to connect to MySQL...")
        connection = pymysql.connect(**mysql_config)
        print(f"{task_name}: Connected to MySQL database successfully")
        
        with connection.cursor() as cursor:
            print(f"{task_name}: Created cursor, preparing queries...")
            
            # Get date threshold (last 180 days)
            date_threshold = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
            print(f"{task_name}: Date threshold: {date_threshold}")
            
            # Count total records
            query_count_contacts = "SELECT COUNT(*) FROM estate_deals_contacts WHERE date_modified >= %s AND contacts_buy_phones IS NOT NULL AND contacts_buy_phones != ''"
            print(f"{task_name}: Executing count query...")
            cursor.execute(query_count_contacts, (date_threshold,))
            count_result = cursor.fetchone()
            if count_result:
                total_records_to_process = count_result[0]
            print(f"{task_name}: Total contacts to process: {total_records_to_process}")
            
            if total_records_to_process == 0:
                print(f"{task_name}: No contacts found to process. Exiting.")
                return {
                    "status": "success", 
                    "task": task_name, 
                    "loaded": 0, 
                    "total_processed_from_source": 0, 
                    "skipped_unformattable": 0, 
                    "skipped_conflicts": 0, 
                    "skipped_staging_errors": 0, 
                    "errors_list": ["No contacts found with valid modification date and non-empty phones"]
                }
            
            # Fetch contacts data
            query_contacts = """
                SELECT id, contacts_buy_name, contacts_buy_phones
                FROM estate_deals_contacts
                WHERE date_modified >= %s
                AND contacts_buy_phones IS NOT NULL 
                AND contacts_buy_phones != ''
                ORDER BY id
            """
            print(f"{task_name}: Executing main query...")
            cursor.execute(query_contacts, (date_threshold,))
            print(f"{task_name}: Query executed successfully")
            
            batch_size = int(os.getenv('DB_FETCH_CONTACTS_BATCH_SIZE', 1000))
            batch_number = 0
            
            # Track unique phones across all batches to avoid global duplicates
            global_processed_phones = set()
            
            print(f"{task_name}: Starting batch processing with batch size {batch_size}")
            
            while True:
                print(f"{task_name}: Fetching next batch...")
                rows_from_mysql = cursor.fetchmany(batch_size)
                if not rows_from_mysql:
                    print(f"{task_name}: No more rows to process")
                    break
                
                batch_number += 1
                current_mysql_batch_size = len(rows_from_mysql)
                print(f"{task_name}: Processing batch {batch_number} with {current_mysql_batch_size} rows")
                
                staged_for_commit_in_batch = 0
                skipped_unformattable_phone_in_batch = 0
                skipped_in_batch_conflict_in_batch = 0
                skipped_staging_error_in_batch = 0
                
                # Show sample of raw data
                if batch_number == 1:
                    print(f"{task_name}: Sample data from first batch:")
                    for i, row in enumerate(rows_from_mysql[:3]):
                        print(f"  Row {i+1}: ID={row[0]}, Name='{row[1]}', Phone='{row[2]}'")
                
                # Expand contacts with multiple phone numbers
                expanded_contacts = []
                for mysql_row in rows_from_mysql:
                    contact_id, full_name, phone_number_raw = mysql_row
                    
                    if not phone_number_raw or phone_number_raw.strip() == '':
                        continue
                    
                    # Handle multiple phone numbers separated by commas
                    if ',' in phone_number_raw:
                        phone_numbers = [phone.strip() for phone in phone_number_raw.split(',') if phone.strip()]
                        for phone in phone_numbers:
                            formatted_phone = utils.format_phone_number(phone)
                            if formatted_phone:
                                expanded_contacts.append({
                                    'contact_id': contact_id,
                                    'full_name': full_name,
                                    'formatted_phone': formatted_phone,
                                    'raw_phone': phone
                                })
                            else:
                                unformattable_phone_details_list.append({'id': contact_id, 'raw_phone': phone})
                                skipped_unformattable_phone_in_batch += 1
                    else:
                        # Single phone number
                        formatted_phone = utils.format_phone_number(phone_number_raw)
                        if formatted_phone:
                            expanded_contacts.append({
                                'contact_id': contact_id,
                                'full_name': full_name,
                                'formatted_phone': formatted_phone,
                                'raw_phone': phone_number_raw
                            })
                        else:
                            unformattable_phone_details_list.append({'id': contact_id, 'raw_phone': phone_number_raw})
                            skipped_unformattable_phone_in_batch += 1
                
                print(f"{task_name}: Expanded {len(expanded_contacts)} contact records from {current_mysql_batch_size} MySQL rows")
                
                # Show sample of expanded data
                if batch_number == 1 and expanded_contacts:
                    print(f"{task_name}: Sample expanded data:")
                    for i, contact in enumerate(expanded_contacts[:3]):
                        print(f"  Expanded {i+1}: ID={contact['contact_id']}, Phone='{contact['formatted_phone']}'")
                
                grand_total_skipped_unformattable_phone += skipped_unformattable_phone_in_batch
                
                # Process expanded contacts - using phone as unique key
                contacts_to_add = []
                
                for contact_data in expanded_contacts:
                    contact_id_from_mysql = contact_data['contact_id']
                    formatted_phone_number = contact_data['formatted_phone']
                    full_name_from_mysql = contact_data['full_name']
                    try:
                        # Check for duplicate phones globally (across all batches)
                        if formatted_phone_number in global_processed_phones:
                            print(f"{task_name}: Phone {formatted_phone_number} already processed globally, skipping")
                            skipped_in_batch_conflict_in_batch += 1
                            continue
                        
                        # Create new contact record with phone as primary unique identifier
                        # Since contacts_id is no longer unique, we can have multiple records with same contacts_id but different phones
                        new_contact = MacroContact(
                            contacts_id=contact_id_from_mysql,
                            full_name=full_name_from_mysql,
                            phone_number=formatted_phone_number
                        )
                        contacts_to_add.append(new_contact)
                        global_processed_phones.add(formatted_phone_number)
                        staged_for_commit_in_batch += 1
                    
                    except Exception as e_single:
                        error_msg = f"{task_name}: Exception processing record: ID {contact_id_from_mysql}, Phone {formatted_phone_number} - {str(e_single)}"
                        print(error_msg) 
                        errors.append(error_msg)
                        skipped_staging_error_in_batch += 1
            
                # Bulk insert contacts
                if contacts_to_add:
                    try:
                        print(f"{task_name}: Adding {len(contacts_to_add)} contacts to session...")
                        db.session.add_all(contacts_to_add)
                        print(f"{task_name}: Committing batch...")
                        db.session.commit()
                        loaded_records += len(contacts_to_add)
                        print(f"{task_name}: Successfully committed {len(contacts_to_add)} contacts to database")
                    except Exception as e_batch:
                        db.session.rollback()
                        error_msg = f"{task_name}: Error committing batch of {len(contacts_to_add)} contacts: {str(e_batch)}"
                        print(error_msg)
                        errors.append(error_msg)
                        # Try to get more details about the error
                        import traceback
                        print(f"{task_name}: Full traceback: {traceback.format_exc()}")
                        
                        # Try individual inserts to identify problematic records
                        print(f"{task_name}: Attempting individual inserts to identify problems...")
                        individual_success = 0
                        for contact in contacts_to_add:
                            try:
                                # Check if phone already exists
                                existing = MacroContact.query.filter_by(phone_number=contact.phone_number).first()
                                if existing:
                                    print(f"{task_name}: Phone {contact.phone_number} already exists, updating contact_id from {existing.contacts_id} to {contact.contacts_id}")
                                    existing.contacts_id = contact.contacts_id
                                    existing.full_name = contact.full_name
                                else:
                                    db.session.add(contact)
                                db.session.commit()
                                individual_success += 1
                            except Exception as e_individual:
                                db.session.rollback()
                                print(f"{task_name}: Failed individual insert for {contact.phone_number}: {e_individual}")
                        
                        loaded_records += individual_success
                        print(f"{task_name}: Individual inserts: {individual_success} successful")
                else:
                    print(f"{task_name}: No contacts to add in this batch")
            
                grand_total_skipped_in_batch_conflict += skipped_in_batch_conflict_in_batch
                grand_total_skipped_staging_error += skipped_staging_error_in_batch
            
                print(f"{task_name}: Batch {batch_number} Report - MySQL rows: {current_mysql_batch_size}, "
                      f"Expanded contacts: {len(expanded_contacts)}, "
                      f"Skipped unformattable: {skipped_unformattable_phone_in_batch}, "
                      f"Successfully added: {len(contacts_to_add)}, "
                      f"Skipped (conflicts): {skipped_in_batch_conflict_in_batch}, "
                      f"Skipped (errors): {skipped_staging_error_in_batch}")
            
                # Progress update
                if total_records_to_process > 0:
                    progress_percentage = (loaded_records / total_records_to_process * 100) if total_records_to_process > 0 else 0
                    print(f"{task_name}: Progress - {loaded_records} contacts loaded ({progress_percentage:.1f}%)")
        
        # Final verification
        final_count = MacroContact.query.count()
        print(f"{task_name}: Final verification - {final_count} contacts in database")
        
        # После загрузки контактов синхронизируем рефералы
        print(f"{task_name}: Starting referals synchronization...")
        try:
            sync_referals_with_macro_contacts()
            print(f"{task_name}: referals synchronization completed successfully")
        except Exception as sync_error:
            print(f"{task_name}: Error during referals synchronization: {sync_error}")
            errors.append(f"referals sync error: {str(sync_error)}")
        