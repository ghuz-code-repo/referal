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
        'cursorclass': pymysql.cursors.Cursor
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
                
                # Fetch contacts data - убираем поле номер договора, оно не нужно
                query_contacts = """
                    SELECT id, contacts_buy_name, contacts_buy_phones, 
                           COALESCE(contacts_buy_emails, '') as contacts_buy_emails
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
                        contact_id, full_name, phone_number_raw, email_raw = mysql_row
                        
                        if not phone_number_raw or phone_number_raw.strip() == '':
                            continue
                        
                        # Обработка email - берем только первый из списка
                        processed_email = None
                        if email_raw and email_raw.strip():
                            # Разбиваем по запятой и берем первый email
                            emails = [email.strip() for email in email_raw.split(',') if email.strip()]
                            if emails:
                                processed_email = emails[0]
                                print(f"DEBUG: Processed email for contact {contact_id}: {processed_email}")
                        
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
                                        'email': processed_email
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
                                    'email': processed_email
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
                                # Добавляем в processed phones после обновления
                                global_processed_phones.add(formatted_phone_number)
                                staged_for_commit_in_batch += 1
                            else:
                                # Create new contact record with all fields
                                new_contact = MacroContact(
                                    contacts_id=contact_id_from_mysql,
                                    full_name=full_name_from_mysql,
                                    phone_number=formatted_phone_number,
                                    passport_number=contact_data.get('passport_number'),
                                    passport_giver=contact_data.get('passport_giver'),
                                    passport_date=contact_data.get('passport_date'),
                                    passport_address=contact_data.get('passport_address'),
                                    email=contact_data.get('email')
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
            # Clear existing deals for fresh import
            print(f"{task_name}: Clearing existing deals...")
            MacroDeal.query.delete()
            db.session.commit()
            print(f"{task_name}: Existing deals cleared.")
            
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

                # Fetch deals data
                query_deals = """
                    SELECT deal_status_name, agreement_number, contacts_buy_id, deal_area
                    FROM estate_deals 
                    WHERE contacts_buy_id IS NOT NULL
                    AND agreement_number IS NOT NULL
                """
                cursor.execute(query_deals)
                print(f"{task_name}: Executed SELECT query for deals.")

                batch_size = int(os.getenv('DB_FETCH_DEALS_BATCH_SIZE', 1000))
                batch_number = 0
                
                while True:
                    rows = cursor.fetchmany(batch_size)
                    if not rows:
                        break
                    
                    batch_number += 1
                    current_batch_size = len(rows)
                    print(f"{task_name}: Processing batch {batch_number} with {current_batch_size} rows")
                    
                    deals_in_batch_to_add = []
                    for row_data in rows: 
                        deal_status_name, agreement_number, contacts_buy_id, deal_area = row_data
                        try:
                            new_deal = MacroDeal(
                                deal_status_name=deal_status_name,
                                agreement_number=agreement_number,
                                contacts_buy_id=contacts_buy_id,
                                deal_metr=deal_area
                            )
                            deals_in_batch_to_add.append(new_deal)
                        except Exception as e:
                            error_msg = f"{task_name}: Error creating MacroDeal object for agreement {agreement_number}: {str(e)}"
                            print(error_msg)
                            errors.append(error_msg)
                    
                    if deals_in_batch_to_add:
                        try:
                            db.session.add_all(deals_in_batch_to_add)
                            db.session.commit() 
                            loaded_deals += len(deals_in_batch_to_add)
                            print(f"{task_name}: Successfully committed {len(deals_in_batch_to_add)} deals to database")
                        except Exception as e:
                            db.session.rollback()
                            error_msg = f"{task_name}: Error committing batch of {len(deals_in_batch_to_add)} deals: {str(e)}"
                            print(error_msg)
                            errors.append(error_msg)
                    
                    # Progress update
                    if total_deals_to_process > 0:
                        percentage = (loaded_deals / total_deals_to_process) * 100
                        print(f"{task_name}: Progress - {loaded_deals} deals loaded ({percentage:.1f}%)")
            
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
