"""Сервис для синхронизации данных с внешними источниками"""

from datetime import datetime, timedelta
from typing import List
import os
import pymysql
from pymysql import MySQLError
from flask import current_app
from models import *
import utils as utils


def fetch_data_from_mysql():
    """Получает данные для контактов и сделок из MySQL синхронно."""
    app = current_app._get_current_object() 

    mysql_config = {
        'host': os.getenv('MYSQL_HOST'),
        'port': int(os.getenv('MYSQL_PORT')),
        'database': os.getenv('MYSQL_DATABASE'),
        'user': os.getenv('MYSQL_USER'),
        'password': os.getenv('MYSQL_PASSWORD'),
        'cursorclass': pymysql.cursors.Cursor,
        'connect_timeout': 600,  # 10 минут на подключение
        'read_timeout': 1800,    # 30 минут на чтение результатов
        'write_timeout': 600     # 10 минут на запись
    }
    
    print("=== Starting synchronous data fetch ===")
    print(f"MySQL Config: {mysql_config['host']}:{mysql_config['port']}/{mysql_config['database']}")
    
    # Execute contacts task first
    print("\n=== CONTACTS TASK ===")
    contacts_result = _fetch_and_process_contacts_task(mysql_config, app.app_context())
    # print(f"Contacts task result: {contacts_result}")
    
    # Execute deals task second
    print("\n=== DEALS TASK ===")
    deals_result = _fetch_and_process_deals_task(mysql_config, app.app_context())
    print(f"Deals task result: {deals_result}")
    
    # НОВЫЙ ШАГ: Нормализация телефонов в ReferalData
    print("\n=== NORMALIZING REFERAL PHONE NUMBERS ===")
    with app.app_context():
        _normalize_referal_phone_numbers()
    
    # Update referal-deal links after synchronization
    print("\n=== UPDATING REFERAL-DEAL LINKS AND PAYMENTS ===")
    with app.app_context():
        from models import Referal, ReferalDeal
        
        # Получаем все рефералы
        all_referals = Referal.query.join(ReferalData).all()
        print(f"Found {len(all_referals)} referals to process")
        
        updated_referals = 0
        created_links = 0
        updated_payments = 0
        
        for referal in all_referals:
            try:
                print(f"\n🔍 Processing Referal ID={referal.id}, Phone={referal.referal_data.phone_number}, Name={referal.referal_data.full_name}")
                
                # 0) Найти реферала (контакт) по номеру телефона или имени
                contact = None
                referal_phone = referal.referal_data.phone_number
                
                # Пробуем найти по телефону
                if referal_phone:
                    referal_phone_variants = utils.extract_and_normalize_phones(referal_phone)
                    for phone_variant in referal_phone_variants:
                        contact = MacroContact.query.filter_by(phone_number=phone_variant).first()
                        if contact:
                            print(f"  ✅ Found contact by phone: {phone_variant}")
                            break
                        contact = MacroContact.query.filter(MacroContact.phone_number.contains(phone_variant)).first()
                        if contact:
                            print(f"  ✅ Found contact by partial phone match: {phone_variant}")
                            break
                
                # Если не найден по телефону, ищем по имени
                if not contact and referal.referal_data.full_name:
                    referal_full_name = referal.referal_data.full_name.strip()
                    contact = MacroContact.query.filter_by(full_name=referal_full_name).first()
                    if contact:
                        print(f"  ✅ Found contact by name: {referal_full_name}")
                
                if not contact:
                    print(f"  ⚠️ Contact not found for referal")
                    continue
                
                # Обновляем contact_id в referal
                if referal.contact_id != contact.contacts_id:
                    referal.contact_id = contact.contacts_id
                    print(f"  ✅ Updated referal.contact_id = {contact.contacts_id}")
                
                # 1) Найти договора РЕФЕРАЛА (клиента) с оплатами > 3000000
                referal_date = referal.created_at.date()
                deals = MacroDeal.query.filter_by(contacts_buy_id=contact.contacts_id).all()
                
                if not deals:
                    print(f"  ⚠️ No deals found for contact {contact.contacts_id}")
                    continue
                
                print(f"  📋 Found {len(deals)} deals for contact {contact.contacts_id}")
                
                suitable_deals_found = False
                
                for deal in deals:
                    # Проверяем условия:
                    # - Договор заключен ПОЗЖЕ даты добавления реферала
                    # - Оплата > 3000000
                    if not deal.agreement_date:
                        print(f"    ⏭️ Deal {deal.agreement_number}: No agreement date")
                        continue
                    
                    if deal.agreement_date <= referal_date:
                        print(f"    ⏭️ Deal {deal.agreement_number}: Date {deal.agreement_date} <= referal date {referal_date}")
                        continue
                    
                    if (deal.total_payments or 0) <= 3000000:
                        print(f"    ⏭️ Deal {deal.agreement_number}: Payment {deal.total_payments} <= 3000000")
                        continue
                    
                    # Договор подходит!
                    days_diff = (deal.agreement_date - referal_date).days
                    print(f"    ✅ MATCH! Deal {deal.agreement_number}: Payment={deal.total_payments}, Date={deal.agreement_date} (+{days_diff} days)")
                    
                    # 2) Привязать договор к рефералу (через ReferalDeal)
                    existing_link = ReferalDeal.query.filter_by(
                        referal_id=referal.id,
                        deal_id=deal.id
                    ).first()
                    
                    if not existing_link:
                        is_within_window = days_diff <= referal.days_window
                        new_link = ReferalDeal(
                            referal_id=referal.id,
                            deal_id=deal.id,
                            is_within_window=is_within_window,
                            days_from_referal_creation=days_diff
                        )
                        db.session.add(new_link)
                        created_links += 1
                        print(f"    ✅ Created ReferalDeal link (within_window={is_within_window})")
                    else:
                        print(f"    ℹ️ ReferalDeal link already exists")
                    
                    # Обновляем referal_id в MacroDeal для relationship
                    if deal.referal_id != referal.id:
                        deal.referal_id = referal.id
                    
                    # 3) Вычислить сумму выплаты от площади квартиры
                    deal_metr = deal.deal_metr or 0
                    withdrawal_amount = 0
                    
                    if 20.0 <= deal_metr < 40.0:
                        withdrawal_amount = int(os.getenv('REFERAL_WITHDRAWAL_FOR_40M', 0))
                    elif 40.0 <= deal_metr < 60.0:
                        withdrawal_amount = int(os.getenv('REFERAL_WITHDRAWAL_FOR_60M', 0))
                    elif 60.0 <= deal_metr < 80.0:
                        withdrawal_amount = int(os.getenv('REFERAL_WITHDRAWAL_FOR_80M', 0))
                    elif deal_metr >= 80.0:
                        withdrawal_amount = int(os.getenv('REFERAL_WITHDRAWAL_FOR_81M', 0))
                    
                    if withdrawal_amount > 0:
                        # 4) Записать сумму выплаты в ReferalDeal (ВСЕГДА обновляем!)
                        if existing_link:
                            if existing_link.withdrawal_amount != withdrawal_amount:
                                existing_link.withdrawal_amount = withdrawal_amount
                                updated_payments += 1
                                print(f"    💰 Updated withdrawal_amount: {withdrawal_amount} (area={deal_metr}m²)")
                        else:
                            # Для нового линка устанавливаем сразу
                            new_link.withdrawal_amount = withdrawal_amount
                            print(f"    💰 Set withdrawal_amount: {withdrawal_amount} (area={deal_metr}m²)")
                        
                        # Также обновляем данные в Referal для совместимости (ВСЕГДА обновляем!)
                        if not referal.referal_data.contract_number:
                            referal.referal_data.contract_number = deal.agreement_number
                        referal.deal_metr = deal_metr  # ВСЕГДА обновляем площадь
                        referal.withdrawal_amount = withdrawal_amount  # ВСЕГДА обновляем выплату
                    
                    suitable_deals_found = True
                    # Берём первый подходящий договор (можно убрать break если нужны все)
                    break
                
                if suitable_deals_found:
                    updated_referals += 1
                else:
                    print(f"  ⚠️ No suitable deals found (all deals filtered out)")
                
            except Exception as e:
                print(f"❌ Error processing referal {referal.id}: {e}")
                import traceback
                traceback.print_exc()
        
        # Сохраняем все изменения
        try:
            db.session.commit()
            print(f"\n✅ Successfully updated {updated_referals} referals")
            print(f"   - Created {created_links} new ReferalDeal links")
            print(f"   - Updated {updated_payments} withdrawal amounts")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error committing changes: {e}")
            raise
    
    # Update last deal dates for all contacts
    print("\n=== UPDATING LAST DEAL DATES ===")
    with app.app_context():
        _update_last_deal_dates_for_contacts()
    
    # Final verification of both tables
    with app.app_context():
        final_contacts_count = MacroContact.query.count()
        final_deals_count = MacroDeal.query.count()
        print(f"\n=== FINAL VERIFICATION ===")
        print(f"MacroContact table: {final_contacts_count} records")
        print(f"MacroDeal table: {final_deals_count} records")
    
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
    """Выбирает приоритетный номер телефона из списка."""
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
        return uzbek_phones[0]
    elif russian_phones:
        return russian_phones[0]
    elif other_phones:
        return other_phones[0]
    else:
        return phone_numbers[0]


def sync_referals_with_macro_contacts():
    """
    Синхронизирует существующие рефералы с обновленными MacroContact записями.
    НЕ перезаписывает вручную введенные имена рефералов.
    """
    print("Starting referals synchronization with MacroContact...")
    
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
            old_contact_id = referal.contact_id
            referal.contact_id = matching_contact_by_phone.contacts_id
            
            # УБРАНО: НЕ обновляем имя реферала автоматически
            # Теперь пользователь может сам выбрать имя через кнопку в интерфейсе
            # if referal.referal_data.full_name != matching_contact_by_phone.full_name:
            #     print(f"Updating referal name from '{referal.referal_data.full_name}' to '{matching_contact_by_phone.full_name}' for phone {referal_phone}")
            #     referal.referal_data.full_name = matching_contact_by_phone.full_name
            
            if old_contact_id != matching_contact_by_phone.contacts_id:
                print(f"Updated referal contact_id from {old_contact_id} to {matching_contact_by_phone.contacts_id} for phone {referal_phone}")
                print(f"MacroContact name available: '{matching_contact_by_phone.full_name}' (user can choose to use it)")
                updated_count += 1
        else:
            # Приоритет 2: Поиск по имени (если телефон не найден)
            if referal_name:
                matching_contacts_by_name = MacroContact.query.filter_by(full_name=referal_name).all()
                
                if matching_contacts_by_name:
                    available_phones = [contact.phone_number for contact in matching_contacts_by_name]
                    best_phone = prioritize_phone_numbers(available_phones)
                    
                    if best_phone and best_phone != referal_phone:
                        best_contact = next((c for c in matching_contacts_by_name if c.phone_number == best_phone), None)
                        
                        if best_contact:
                            old_phone = referal.referal_data.phone_number
                            referal.referal_data.phone_number = best_contact.phone_number
                            referal.contact_id = best_contact.contacts_id
                            
                            print(f"Updated referal phone from '{old_phone}' to '{best_contact.phone_number}' for name '{referal_name}' (prioritized Uzbek number)")
                            phone_updated_count += 1
                            updated_count += 1
    
    try:
        db.session.commit()
        print(f"Synchronization completed: {updated_count} referals updated, {phone_updated_count} phone numbers updated")
        print("Note: Referal names are preserved - users can manually choose to use MacroCRM names via UI")
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
    try:
        with app_context:
            print(f"{task_name}: Inside app context")
            
            # Instead of clearing all contacts, we'll use upsert logic
            # This preserves existing data and only updates/adds new records
            print(f"{task_name}: Starting incremental sync (preserving existing data)...")
            existing_contacts_count = MacroContact.query.count()
            print(f"{task_name}: Current contacts in database: {existing_contacts_count}")
            
            print(f"{task_name}: Attempting to connect to MySQL...")
            connection = pymysql.connect(**mysql_config)
            print(f"{task_name}: Connected to MySQL database successfully")
            
            with connection.cursor() as cursor:
                print(f"{task_name}: Created cursor, preparing queries...")
                
                # Get date threshold (last N days)
                threshold_days = int(os.getenv("TRASHHOLDDAYS", 45))
                date_threshold = (datetime.now() - timedelta(days=threshold_days)).strftime('%Y-%m-%d')
                print(f"{task_name}: Date threshold: {date_threshold} (last {threshold_days} days)")
                
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
                
                # Fetch contacts data with date_modified for tracking interactions
                # NOTE: date_created не существует в MySQL, используем date_modified для обеих дат
                query_contacts = """
                    SELECT id, contacts_buy_name, contacts_buy_phones, 
                           COALESCE(contacts_buy_emails, '') as contacts_buy_emails,
                           date_modified, date_modified as date_created
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
                
                total_processed_so_far = 0
                while True:
                    rows_from_mysql = cursor.fetchmany(batch_size)
                    if not rows_from_mysql:
                        print(f"✅ {task_name}: All batches processed!")
                        break
                    
                    batch_number += 1
                    current_mysql_batch_size = len(rows_from_mysql)
                    total_processed_so_far += current_mysql_batch_size
                    
                    # Показываем прогресс в процентах
                    progress_pct = (total_processed_so_far / total_records_to_process) * 100 if total_records_to_process > 0 else 0
                    print(f"📊 CONTACTS Batch {batch_number} | Fetched: {current_mysql_batch_size} rows | Total: {total_processed_so_far}/{total_records_to_process} ({progress_pct:.1f}%)")
                    
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
                        contact_id, full_name, phone_number_raw, email_raw, date_modified, date_created = mysql_row
                        
                        if not phone_number_raw or phone_number_raw.strip() == '':
                            continue
                        
                        # Обработка email - берем только первый из списка
                        processed_email = None
                        if email_raw and email_raw.strip():
                            # Разбиваем по запятой и берем первый email
                            emails = [email.strip() for email in email_raw.split(',') if email.strip()]
                            if emails:
                                processed_email = emails[0]
                                # print(f"DEBUG: Processed email for contact {contact_id}: {processed_email}")
                        
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
                                        'raw_phone': phone,
                                        'passport_number': None,
                                        'passport_giver': None,
                                        'passport_date': None,
                                        'passport_address': None,
                                        'email': processed_email,
                                        'date_modified': date_modified,
                                        'date_created': date_created
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
                                    'raw_phone': phone_number_raw,
                                    'passport_number': None,
                                    'passport_giver': None,
                                    'passport_date': None,
                                    'passport_address': None,
                                    'email': processed_email,
                                    'date_modified': date_modified,
                                    'date_created': date_created
                                })
                            else:
                                unformattable_phone_details_list.append({'id': contact_id, 'raw_phone': phone_number_raw})
                                skipped_unformattable_phone_in_batch += 1
                    
                    # print(f"{task_name}: Expanded {len(expanded_contacts)} contact records from {current_mysql_batch_size} MySQL rows")
                    
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
                                # print(f"{task_name}: Phone {formatted_phone_number} already processed globally, skipping")
                                skipped_in_batch_conflict_in_batch += 1
                                continue
                            
                            # Check if contact already exists
                            existing_contact = MacroContact.query.filter_by(phone_number=formatted_phone_number).first()
                            
                            if existing_contact:
                                # Update existing contact with new data
                                existing_contact.full_name = full_name_from_mysql
                                existing_contact.contacts_id = contact_id_from_mysql
                                existing_contact.email = contact_data.get('email')
                                existing_contact.passport_address = contact_data.get('passport_address')
                                existing_contact.passport_number = contact_data.get('passport_number')
                                existing_contact.passport_giver = contact_data.get('passport_giver')
                                existing_contact.passport_date = contact_data.get('passport_date')
                                # Обновляем даты взаимодействий
                                existing_contact.date_modified = contact_data.get('date_modified')
                                existing_contact.last_interaction_date = contact_data.get('date_modified')
                                if not existing_contact.first_interaction_date:
                                    existing_contact.first_interaction_date = contact_data.get('date_created')
                                # Добавляем в processed phones после обновления
                                global_processed_phones.add(formatted_phone_number)
                                staged_for_commit_in_batch += 1
                            else:
                                # Create new contact record with all fields including interaction dates
                                new_contact = MacroContact(
                                    contacts_id=contact_id_from_mysql,
                                    full_name=full_name_from_mysql,
                                    phone_number=formatted_phone_number,
                                    passport_number=contact_data.get('passport_number'),
                                    passport_giver=contact_data.get('passport_giver'),
                                    passport_date=contact_data.get('passport_date'),
                                    passport_address=contact_data.get('passport_address'),
                                    email=contact_data.get('email'),
                                    date_modified=contact_data.get('date_modified'),
                                    first_interaction_date=contact_data.get('date_created'),
                                    last_interaction_date=contact_data.get('date_modified')
                                )
                                contacts_to_add.append(new_contact)
                                # print(f"DEBUG: Creating new contact with email: {contact_data.get('email')}")
                                # Добавляем в processed phones для новых контактов
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
                            db.session.add_all(contacts_to_add)
                            db.session.commit()
                            loaded_records += len(contacts_to_add)
                            print(f"💾 CONTACTS Batch {batch_number} | Committed: {len(contacts_to_add)} new contacts | Total loaded: {loaded_records}")
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
                                    # Check if phone already exists again (safety check)
                                    existing = MacroContact.query.filter_by(phone_number=contact.phone_number).first()
                                    if existing:
                                        print(f"{task_name}: Phone {contact.phone_number} already exists during individual insert, updating...")
                                        existing.contacts_id = contact.contacts_id
                                        existing.full_name = contact.full_name
                                        existing.email = contact.email
                                        existing.passport_address = contact.passport_address
                                        existing.passport_number = contact.passport_number
                                        existing.passport_giver = contact.passport_giver
                                        existing.passport_date = contact.passport_date
                                    else:
                                        db.session.add(contact)
                                    db.session.commit()
                                    individual_success += 1
                                except Exception as e_individual:
                                    db.session.rollback()
                                    print(f"{task_name}: Failed individual insert for {contact.phone_number}: {e_individual}")
                            
                            loaded_records += individual_success
                            print(f"{task_name}: Individual inserts: {individual_success} successful")
                    
                    # Commit updates to existing contacts
                    try:
                        db.session.commit()
                        print(f"{task_name}: Successfully committed updates to existing contacts")
                    except Exception as e_update:
                        db.session.rollback()
                        print(f"{task_name}: Error committing updates to existing contacts: {e_update}")
                        errors.append(f"Update commit error: {str(e_update)}")

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
            
    except MySQLError as e: 
        print(f"{task_name}: MySQL Error: {e}") 
        errors.append(f"MySQL Error: {str(e)}")
    except Exception as e: 
        print(f"{task_name}: General Error during processing: {e}") 
        errors.append(f"General Error: {str(e)}")
    finally:
        if connection:
            connection.close()
            print(f"{task_name}: MySQL connection closed")

        print(f"{task_name}: Finished processing. Total loaded: {loaded_records}")
        print(f"{task_name}: Total skipped (unformattable): {grand_total_skipped_unformattable_phone}")
        print(f"{task_name}: Total skipped (conflicts): {grand_total_skipped_in_batch_conflict}")
        print(f"{task_name}: Total skipped (staging errors): {grand_total_skipped_staging_error}")

        if unformattable_phone_details_list and len(unformattable_phone_details_list) <= 10:
            print(f"{task_name}: Sample unformattable phones:")
            for detail in unformattable_phone_details_list[:10]:
                print(f"  - ID: {detail['id']}, Raw Phone: '{detail['raw_phone']}'")
        
        status = "success" if loaded_records > 0 else "failure"
        return {
            "status": status, 
            "task": task_name, 
            "loaded": loaded_records, 
            "total_processed_from_source": total_records_to_process, 
            "skipped_unformattable": grand_total_skipped_unformattable_phone, 
            "skipped_conflicts": grand_total_skipped_in_batch_conflict, 
            "skipped_staging_errors": grand_total_skipped_staging_error, 
            "errors_list": errors
        }


def _fetch_and_process_deals_task(mysql_config, app_context):
    """Получает сделки из MySQL и вставляет их в локальную таблицу MacroDeal."""
    task_name = "Deals Task"
    loaded_deals = 0
    total_deals_to_process = 0
    errors = []
    connection = None
    print(f"{task_name}: Starting.")
    try:
        with app_context:
            # Instead of clearing all deals, use incremental sync
            print(f"{task_name}: Starting incremental sync (preserving existing data)...")
            existing_deals_count = MacroDeal.query.count()
            print(f"{task_name}: Current deals in database: {existing_deals_count}")
            
            # Use mysql_config directly - it already contains all timeout settings
            connection = pymysql.connect(**mysql_config)
            print(f"{task_name}: Connected to MySQL database successfully")
            
            with connection.cursor() as cursor:
                # Count total deals
                query_count_deals = "SELECT COUNT(*) FROM estate_deals"
                cursor.execute(query_count_deals)
                count_result = cursor.fetchone()
                if count_result:
                    total_deals_to_process = count_result[0]
                print(f"{task_name}: Total deals to process: {total_deals_to_process}")

                print(f"{task_name}: ⏳ Executing complex SQL query with JOINs... This may take a few minutes...")
                
                # Fetch deals data with total payments from finances table + property details
                # Суммируем все ПРОВЕДЕННЫЕ платежи по договору из таблицы finances (кроме брони)
                # Также получаем данные о недвижимости для генерации актов
                query_deals = """
                    SELECT 
                        ed.deal_status_name, 
                        ed.agreement_number, 
                        ed.contacts_buy_id, 
                        ed.deal_area,
                        COALESCE(SUM(
                            CASE 
                                WHEN f.status_name = 'Проведено' AND f.types_name != 'Бронь' 
                                THEN f.summa 
                                ELSE 0 
                            END
                        ), 0) as total_payments,
                        h.complex_name as project_name,
                        h.geo_street_name as house_address,
                        h.geo_house as house_number,
                        es.geo_flatnum as apartment_number,
                        es.estate_rooms as rooms,
                        es.estate_riser as entrance,
                        es.estate_floor as floor,
                        (SELECT MAX(es2.estate_floor) 
                         FROM estate_sells es2 
                         WHERE es2.house_id = h.id) as max_floor,
                        ed.finances_income as agreement_price,
                        ed.agreement_date
                    FROM estate_deals ed
                    LEFT JOIN finances f ON ed.id = f.deal_id
                    LEFT JOIN estate_sells es ON ed.estate_sell_id = es.estate_sell_id
                    LEFT JOIN estate_houses h ON es.house_id = h.id
                    WHERE ed.contacts_buy_id IS NOT NULL
                    AND ed.agreement_number IS NOT NULL
                    GROUP BY ed.id, ed.deal_status_name, ed.agreement_number, ed.contacts_buy_id, ed.deal_area,
                             h.complex_name, h.geo_street_name, h.geo_house, es.geo_flatnum, es.estate_rooms,
                             es.estate_riser, es.estate_floor, h.id,
                             ed.finances_income, ed.agreement_date
                """
                
                # Start timer
                import time
                query_start = time.time()
                print(f"{task_name}: 🔄 Query execution started at {time.strftime('%H:%M:%S')}")
                
                cursor.execute(query_deals)
                
                query_duration = time.time() - query_start
                print(f"{task_name}: ✅ Query executed successfully in {query_duration:.2f} seconds")
                print(f"{task_name}: 🔄 Starting to fetch and process results...")

                batch_size = int(os.getenv('DB_FETCH_DEALS_BATCH_SIZE', 1000))
                batch_number = 0
                total_deals_processed = 0
                
                while True:
                    fetch_start = time.time()
                    rows = cursor.fetchmany(batch_size)
                    fetch_duration = time.time() - fetch_start
                    
                    if not rows:
                        print(f"✅ {task_name}: All batches processed! No more rows to fetch.")
                        break
                    
                    batch_number += 1
                    current_batch_size = len(rows)
                    total_deals_processed += current_batch_size
                    
                    # Показываем прогресс
                    progress_pct = (total_deals_processed / total_deals_to_process) * 100 if total_deals_to_process > 0 else 0
                    print(f"📊 DEALS Batch {batch_number} | Fetched: {current_batch_size} rows in {fetch_duration:.2f}s | Total: {total_deals_processed}/{total_deals_to_process} ({progress_pct:.1f}%)")
                    
                    deals_in_batch_to_add = []
                    deals_updated_count = 0
                    processing_start = time.time()
                    
                    for row_data in rows: 
                        (deal_status_name, agreement_number, contacts_buy_id, deal_area, total_payments,
                         project_name, house_address, house_number, apartment_number, rooms, entrance, 
                         floor, max_floor, agreement_price, agreement_date) = row_data
                        try:
                            # Check if deal already exists by agreement_number
                            existing_deal = MacroDeal.query.filter_by(agreement_number=agreement_number).first()
                            
                            if existing_deal:
                                # Update existing deal with all fields including property details
                                existing_deal.deal_status_name = deal_status_name
                                existing_deal.contacts_buy_id = contacts_buy_id
                                existing_deal.deal_metr = deal_area
                                existing_deal.total_payments = total_payments or 0
                                existing_deal.project_name = project_name
                                existing_deal.house_address = house_address
                                existing_deal.house_number = house_number
                                existing_deal.apartment_number = apartment_number
                                existing_deal.rooms = rooms
                                existing_deal.entrance = entrance
                                existing_deal.floor = floor
                                existing_deal.max_floor = max_floor
                                existing_deal.agreement_price = agreement_price
                                existing_deal.agreement_date = agreement_date
                                deals_updated_count += 1
                            else:
                                # Create new deal with all fields including property details
                                new_deal = MacroDeal(
                                    deal_status_name=deal_status_name,
                                    agreement_number=agreement_number,
                                    contacts_buy_id=contacts_buy_id,
                                    deal_metr=deal_area,
                                    total_payments=total_payments or 0,
                                    project_name=project_name,
                                    house_address=house_address,
                                    house_number=house_number,
                                    apartment_number=apartment_number,
                                    rooms=rooms,
                                    entrance=entrance,
                                    floor=floor,
                                    max_floor=max_floor,
                                    agreement_price=agreement_price,
                                    agreement_date=agreement_date
                                )
                                deals_in_batch_to_add.append(new_deal)
                        except Exception as e:
                            error_msg = f"{task_name}: Error processing deal for agreement {agreement_number}: {str(e)}"
                            print(error_msg)
                            errors.append(error_msg)
                    
                    # Insert new deals
                    if deals_in_batch_to_add:
                        try:
                            db.session.add_all(deals_in_batch_to_add)
                            loaded_deals += len(deals_in_batch_to_add)
                        except Exception as e:
                            db.session.rollback()
                            error_msg = f"{task_name}: Error adding new deals: {str(e)}"
                            print(error_msg)
                            errors.append(error_msg)
                    
                    # Commit all changes (updates + inserts)
                    try:
                        commit_start = time.time()
                        db.session.commit()
                        commit_duration = time.time() - commit_start
                        processing_duration = time.time() - processing_start
                        
                        total_in_batch = len(deals_in_batch_to_add) + deals_updated_count
                        print(f"💾 DEALS Batch {batch_number} | Committed: {len(deals_in_batch_to_add)} new + {deals_updated_count} updated | Total loaded: {loaded_deals} | Processing: {processing_duration:.2f}s | Commit: {commit_duration:.2f}s")
                    except Exception as e:
                        db.session.rollback()
                        error_msg = f"{task_name}: Error committing batch: {str(e)}"
                        print(error_msg)
                        errors.append(error_msg)
            
            # Final verification
            final_count = MacroDeal.query.count()
            print(f"{task_name}: Final verification - {final_count} deals in database")
            
        return {"status": "success", "task": task_name, "loaded": loaded_deals, "total_processed": total_deals_to_process, "errors": errors}
    except MySQLError as e:
        print(f"{task_name}: MySQL Error: {e}")
        errors.append(f"MySQL Error: {str(e)}")
        return {"status": "failure", "task": task_name, "loaded": loaded_deals, "total_processed": total_deals_to_process, "errors": errors}
    except Exception as e:
        print(f"{task_name}: General Error: {e}")
        errors.append(f"General Error: {str(e)}")
        return {"status": "failure", "task": task_name, "loaded": loaded_deals, "total_processed": total_deals_to_process, "errors": errors}
    finally:
        if connection:
            connection.close()
            print(f"{task_name}: MySQL connection closed")


def fetch_and_process_contacts(days_back=30):
    """
    Публичная функция для обновления контактов из MacroCRM
    """
    try:
        mysql_config = {
            'host': os.getenv('MYSQL_HOST'),
            'port': int(os.getenv('MYSQL_PORT', 3306)),
            'user': os.getenv('MYSQL_USER'),
            'password': os.getenv('MYSQL_PASSWORD'),
            'database': os.getenv('MYSQL_DATABASE'),
            'charset': 'utf8mb4'
        }
        
        # Запускаем задачу синхронизации
        with current_app.app_context():
            result = _fetch_and_process_contacts_task(mysql_config, current_app.app_context())
            return {
                'success': True,
                'processed_count': result.get('loaded', 0) if result else 0
            }
    except Exception as e:
        print(f"Error in fetch_and_process_contacts: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def _update_last_deal_dates_for_contacts():
    """
    Обновляет поле last_deal_date для всех контактов на основе их последних сделок.
    Используется для проверки 45-дневного окна при добавлении рефералов.
    """
    from models import MacroContact, MacroDeal
    from datetime import datetime
    
    print("Starting update of last_deal_date for all contacts...")
    
    # Получаем все контакты
    all_contacts = MacroContact.query.all()
    updated_count = 0
    
    for contact in all_contacts:
        # Находим все сделки этого контакта
        deals = MacroDeal.query.filter_by(contacts_buy_id=contact.contacts_id).all()
        
        if not deals:
            # Нет сделок - оставляем last_deal_date = None
            if contact.last_deal_date is not None:
                contact.last_deal_date = None
                updated_count += 1
            continue
        
        # Находим последнюю дату сделки (максимальную agreement_date)
        deals_with_dates = [d for d in deals if d.agreement_date]
        
        if not deals_with_dates:
            # Есть сделки, но у них нет дат
            if contact.last_deal_date is not None:
                contact.last_deal_date = None
                updated_count += 1
            continue
        
        # Находим максимальную дату
        last_deal_date = max(d.agreement_date for d in deals_with_dates)
        
        # Обновляем только если изменилось
        if contact.last_deal_date != last_deal_date:
            old_date = contact.last_deal_date
            contact.last_deal_date = last_deal_date
            updated_count += 1
            print(f"  Updated contact {contact.contacts_id} ({contact.full_name}): {old_date} -> {last_deal_date}")
    
    # Сохраняем изменения
    try:
        db.session.commit()
        print(f"✅ Updated last_deal_date for {updated_count} contacts")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error updating last_deal_dates: {e}")
        raise


def _normalize_referal_phone_numbers():
    """
    Нормализует телефоны в ReferalData в формат '+998 XX XXX XX XX' 
    для соответствия формату MacroContact.
    Это критично для правильной работы синхронизации договоров.
    """
    from models import ReferalData, db
    from utils import format_phone_number
    
    print("Starting phone number normalization...")
    
    # Получаем все записи ReferalData
    referal_data_list = ReferalData.query.all()
    updated_count = 0
    
    for referal_data in referal_data_list:
        if referal_data.phone_number:
            # Нормализуем телефон в формат с пробелами
            normalized = format_phone_number(referal_data.phone_number)
            
            # Обновляем только если формат изменился
            if normalized and normalized != referal_data.phone_number:
                old_phone = referal_data.phone_number
                referal_data.phone_number = normalized
                updated_count += 1
                print(f"  Normalized phone for referal {referal_data.referal_id}: '{old_phone}' -> '{normalized}'")
    
    # Сохраняем изменения
    try:
        db.session.commit()
        print(f"✅ Normalized {updated_count} phone numbers in ReferalData")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error normalizing phone numbers: {e}")
        raise

