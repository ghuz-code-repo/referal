"""Сервис для работы с рефералами"""

from datetime import datetime
import logging
import os
import threading
from models import *
import utils
from notification_client import get_notification_client


def send_deal_available_notification(user, referal, deal, withdrawal_amount):
    """
    Отправляет уведомление пользователю о том, что новый договор готов к отправке на проверку
    """
    def _send_async():
        try:
            # Получаем email пользователя
            user_email = None
            
            # Пытаемся получить email из auth-service через API
            if user.auth_user_id:
                try:
                    import requests
                    auth_service_url = os.getenv('AUTH_SERVICE_URL', 'http://auth-service:80')
                    response = requests.get(
                        f"{auth_service_url}/api/users/{user.auth_user_id}",
                        timeout=5
                    )
                    if response.status_code == 200:
                        user_data = response.json()
                        user_email = user_data.get('email')
                except Exception as e:
                    print(f"⚠️ Could not fetch email from auth-service: {e}")
            
            if not user_email:
                print(f"⚠️ No email found for user {user.login}, skipping notification")
                return
            
            notification_client = get_notification_client()
            
            subject = "Новый договор готов к отправке на проверку"
            body = f"""
Здравствуйте, {user.login}!

Хорошие новости! По вашему рефералу "{referal.referal_data.full_name if referal.referal_data else 'Без имени'}" появился новый договор, готовый к отправке на проверку.

Детали договора:
- Номер договора: {deal.agreement_number}
- Сумма выплаты: {withdrawal_amount:,} сум

Вы можете отправить этот договор на проверку в личном кабинете реферальной программы:
{os.getenv('APP_BASE_URL', ' https://analytics.gh.uz')}/referal/my_referrals

После отправки на проверку договор будет рассмотрен нашими специалистами, и вы получите выплату.

---
С уважением,
Команда реферальной программы
"""
            
            success = notification_client.send_email(
                recipient=user_email,
                subject=subject,
                body=body
            )
            
            if success:
                print(f"📧 Deal available notification sent to {user_email} about deal {deal.agreement_number}")
            else:
                print(f"⚠️ Failed to send notification to {user_email}")
                
        except Exception as e:
            print(f"❌ Error sending deal available notification: {e}")
    
    # Запускаем отправку в отдельном потоке
    thread = threading.Thread(target=_send_async)
    thread.daemon = True
    thread.start()


def create_new_referal(full_name, phone_number, user):
    """Создает новый объект реферала.

    Аргументы:
        full_name (str): Полное имя реферала.
        phone_number (str): Номер телефона реферала.
        user (User): Пользователь, создающий реферала.

    Возвращает:
        Referal или None: Объект нового реферала, если он успешно создан и не существует,
                         в противном случае возвращает None.
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


def update_deal_and_balance(referal, user):
    """Обновляет информацию о сделке и баланс пользователя на основе данных реферала.
    НЕ перезаписывает вручную введенные данные реферала.
    """
    print(f"DEBUG update_deal_and_balance: ---- Starting for Referal ID: {referal.id}, Phone: {referal.referal_data.phone_number} ----")
    
    # For referals with multiple phone numbers, find the exact matching contact
    referal_phone = referal.referal_data.phone_number
    contact = None
    
    print(f"DEBUG update_deal_and_balance: Original referal phone: {referal_phone}")
    
    # ПРИОРИТЕТ 1: Поиск по номеру телефона с поддержкой разных форматов
    # Генерируем все возможные варианты телефонов из данных реферала
    referal_phone_variants = utils.extract_and_normalize_phones(referal_phone)
    print(f"DEBUG update_deal_and_balance: Generated {len(referal_phone_variants)} phone variants: {referal_phone_variants}")
    
    # Ищем контакт, перебирая все варианты
    for phone_variant in referal_phone_variants:
        # Сначала пробуем прямое совпадение
        contact = MacroContact.query.filter_by(phone_number=phone_variant).first()
        if contact:
            print(f"DEBUG update_deal_and_balance: Found exact match for phone variant: {phone_variant}")
            break
        
        # Если не нашли, ищем по частичному совпадению (для случаев с несколькими телефонами в MacroContact)
        # Используем LIKE для поиска телефона внутри строки (например, в "(+998...,+998...)")
        contact = MacroContact.query.filter(
            MacroContact.phone_number.contains(phone_variant)
        ).first()
        if contact:
            print(f"DEBUG update_deal_and_balance: Found partial match for phone variant: {phone_variant} in {contact.phone_number}")
            break
    
    # ПРИОРИТЕТ 2: Если не найден по телефону, ищем по имени
    if not contact and referal.referal_data.full_name:
        referal_full_name = referal.referal_data.full_name.strip()
        print(f"DEBUG update_deal_and_balance: Phone not found, searching by name: {referal_full_name}")
        contact = MacroContact.query.filter_by(full_name=referal_full_name).first()
        if contact:
            print(f"DEBUG update_deal_and_balance: Found contact by name match: {contact.full_name}")
    
    current_user = user

    if contact:
        print(f"DEBUG update_deal_and_balance: Found MacroContact - Local DB ID: {contact.id}, contacts_id (from source): {contact.contacts_id}, Name: {contact.full_name}, Phone: {contact.phone_number}")
        
        # УБРАНО: НЕ обновляем имя реферала из MacroContact, сохраняем вручную введенные данные
        print(f"DEBUG update_deal_and_balance: Keeping manual referal name: '{referal.referal_data.full_name}' (MacroContact has: '{contact.full_name}')")

        referal.contact_id = contact.contacts_id 
        
        print(f"DEBUG update_deal_and_balance: Searching for MacroDeal(s) with contacts_buy_id = {contact.contacts_id}")
        deals = MacroDeal.query.filter_by(contacts_buy_id=contact.contacts_id).all()
        
        if not deals:
            print(f"DEBUG update_deal_and_balance: No MacroDeals found in local DB for contacts_buy_id: {contact.contacts_id}")
            return 
        
        print(f"DEBUG update_deal_and_balance: Found {len(deals)} MacroDeal(s) for contacts_buy_id: {contact.contacts_id}. Checking conditions...")
        
        # Дата добавления реферала (для проверки 45-дневного окна)
        referal_date = referal.created_at.date()
        print(f"DEBUG update_deal_and_balance: Referal creation date: {referal_date}")
        
        suitable_deal_found = False
        for deal_obj in deals:
            deal_date = deal_obj.agreement_date
            deal_payment = deal_obj.total_payments or 0
            
            print(f"DEBUG update_deal_and_balance: Checking Deal '{deal_obj.agreement_number}':")
            print(f"  - Status: {deal_obj.deal_status_name}")
            print(f"  - Date: {deal_date}")
            print(f"  - Payment: {deal_payment}")
            print(f"  - Area (metr): {deal_obj.deal_metr}")
            
            # КРИТИЧЕСКИЕ УСЛОВИЯ:
            # 1. Дата договора должна быть ПОЗЖЕ даты добавления реферала
            # 2. Оплата должна быть больше 3 000 000
            
            if not deal_date:
                print(f"  ❌ SKIPPED: No agreement date")
                continue
            
            if deal_date < referal_date:
                print(f"  ❌ SKIPPED: Deal date ({deal_date}) <= Referal date ({referal_date})")
                continue
            
            if deal_payment <= 3000000:
                print(f"  ❌ SKIPPED: Payment ({deal_payment}) <= 3000000")
                continue
            
            # Все условия выполнены!
            days_diff = (deal_date - referal_date).days
            print(f"  ✅ MATCH! Deal qualifies:")
            print(f"     - Days after referal creation: {days_diff}")
            print(f"     - Payment: {deal_payment} > 3000000")
            print(f"     - Date: {deal_date} > {referal_date}")
            
            # ИСПРАВЛЕНО: используем новую таблицу ReferalDeal вместо старого relationship
            from models import ReferalDeal
            existing_link = ReferalDeal.query.filter_by(
                referal_id=referal.id,
                deal_id=deal_obj.id
            ).first()
            
            if not existing_link:
                # Создаём связь реферал-договор
                is_within_window = days_diff <= referal.days_window
                new_link = ReferalDeal(
                    referal_id=referal.id,
                    deal_id=deal_obj.id,
                    is_within_window=is_within_window,
                    days_from_referal_creation=days_diff
                )
                db.session.add(new_link)
                print(f"  ✅ Created ReferalDeal link: referal_id={referal.id}, deal_id={deal_obj.id}, days={days_diff}, within_window={is_within_window}")
            else:
                print(f"  ℹ️ ReferalDeal link already exists")
            
            # ВАЖНО: Устанавливаем referal_id в MacroDeal для работы relationship
            if deal_obj.referal_id != referal.id:
                deal_obj.referal_id = referal.id
                print(f"  ✅ Set MacroDeal.referal_id={referal.id}")
            
            referal.referal_data.contract_number = deal_obj.agreement_number
            referal.deal_metr = deal_obj.deal_metr
            print(f"  ✅ Set contract_number='{deal_obj.agreement_number}', deal_metr={deal_obj.deal_metr}")
            suitable_deal_found = True
            break  # Берём первый подходящий договор

        if not suitable_deal_found:
            print(f"❌ No suitable deals found for contact {contact.contacts_id}:")
            print(f"   All {len(deals)} deals either have:")
            print(f"   - Agreement date <= {referal_date} (referal creation date)")
            print(f"   - OR Payment <= 3000000")

        
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
                
                # ВАЖНО: Обновляем withdrawal_amount в MacroDeal для отображения в UI
                if deal_obj:
                    deal_obj.withdrawal_amount = referal.withdrawal_amount
                    deal_obj.payment_calculated = True
                    print(f"  ✅ Set MacroDeal.withdrawal_amount={referal.withdrawal_amount}")
                
                print(f"DEBUG update_deal_and_balance: Updated user balance by {referal.withdrawal_amount}. New balance: {current_user.current_balance}")
            else:
                print(f"DEBUG update_deal_and_balance: No withdrawal amount set for deal_metr: {referal.deal_metr}")
                
        elif suitable_deal_found and referal.balance_updated:
            # ВАЖНО: Даже если баланс уже обновлен, нужно обновить MacroDeal.withdrawal_amount для UI
            if deal_obj and deal_obj.withdrawal_amount != referal.withdrawal_amount:
                deal_obj.withdrawal_amount = referal.withdrawal_amount
                deal_obj.payment_calculated = True
                print(f"  ✅ Updated MacroDeal.withdrawal_amount={referal.withdrawal_amount} (balance already updated)")
            print(f"DEBUG update_deal_and_balance: Deal found but balance already updated for this referal")

    else:
        print(f"DEBUG update_deal_and_balance: No MacroContact found for referal phone: {referal_phone}")
    
    # Сохраняем все изменения в БД
    try:
        db.session.commit()
        print(f"DEBUG update_deal_and_balance: ✅ Changes committed to database")
    except Exception as e:
        db.session.rollback()
        print(f"DEBUG update_deal_and_balance: ❌ Error committing changes: {e}")
        raise
    
    print(f"DEBUG update_deal_and_balance: ---- Finished for Referal ID: {referal.id}. Final contract_number: '{referal.referal_data.contract_number}' ----")


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
    referals = Referal.query.filter_by(user_id=user_id).join(ReferalData).filter(ReferalData.referal_id == Referal.id).all()
    # Для каждого реферала
    for referal in referals:
        # Обновление информации о сделке и баланса
        update_deal_and_balance(referal, user)

    # Сохранение изменений в базе данных
    db.session.commit()
    logging.debug(f"Final user balance: {user.current_balance}")


# ========================================
# NEW FUNCTIONS FOR MULTIPLE DEALS LOGIC
# ========================================

def check_contact_history_before_adding(phone_number, full_name, days_threshold=45):
    """
    Проверяет, были ли взаимодействия клиента с CRM в течение N дней до текущей даты.
    
    Args:
        phone_number: Номер телефона клиента
        full_name: Полное имя клиента
        days_threshold: Количество дней для проверки (по умолчанию 45)
    
    Returns:
        dict: {
            'can_add': bool,  # Можно ли добавить реферала
            'reason': str,    # Причина отказа (если can_add=False)
            'contact': MacroContact or None,  # Найденный контакт
            'deals': list[MacroDeal],  # Найденные договора
            'first_interaction': datetime or None  # Дата первого взаимодействия
        }
    """
    from datetime import timedelta
    
    # Форматируем телефон
    formatted_phone = utils.format_phone_number(phone_number)
    if not formatted_phone:
        formatted_phone = phone_number
    
    # Определяем граничную дату
    threshold_date = datetime.now() - timedelta(days=days_threshold)
    
    print(f"DEBUG check_contact_history: Checking for phone={formatted_phone}, name={full_name}, threshold={threshold_date}")
    
    # Ищем контакт в MacroContact
    contact = MacroContact.query.filter_by(phone_number=formatted_phone).first()
    
    # Если контакта нет, также ищем по имени
    if not contact and full_name:
        contact = MacroContact.query.filter_by(full_name=full_name.strip()).first()
        if contact:
            print(f"DEBUG check_contact_history: Found contact by name match: {contact.full_name}")
    
    if not contact:
        # Контакт не найден в CRM - можно добавлять
        print(f"DEBUG check_contact_history: Contact not found in CRM - OK to add")
        return {
            'can_add': True,
            'reason': 'Contact not found in CRM',
            'contact': None,
            'deals': [],
            'first_interaction': None
        }
    
    # Контакт найден - проверяем дату ПОСЛЕДНЕЙ СДЕЛКИ (не date_modified!)
    # Используем last_deal_date - дата последней сделки клиента
    last_interaction = contact.last_deal_date
    
    # Конвертируем date в datetime для сравнения с threshold_date
    if last_interaction:
        from datetime import datetime
        last_interaction = datetime.combine(last_interaction, datetime.min.time())
    
    if not last_interaction:
        # Нет данных о сделках - разрешаем добавление
        print(f"DEBUG check_contact_history: No deal date found for contact - OK to add")
        return {
            'can_add': True,
            'reason': 'No deal date found',
            'contact': contact,
            'deals': [],
            'first_interaction': None
        }
    
    # Проверяем, было ли взаимодействие в пределах threshold_date
    if last_interaction >= threshold_date:
        # Последняя сделка была недавно - ЗАПРЕЩАЕМ добавление
        days_ago = (datetime.now() - last_interaction).days
        
        # Ищем все договора этого контакта
        deals = MacroDeal.query.filter_by(contacts_buy_id=contact.contacts_id).all()
        
        print(f"DEBUG check_contact_history: Contact had recent deal ({days_ago} days ago) - CANNOT add")
        return {
            'can_add': False,
            'reason': f'У клиента была сделка {days_ago} дней назад (в пределах {days_threshold} дней)',
            'contact': contact,
            'deals': deals,
            'first_interaction': last_interaction
        }
    
    # Последняя сделка была давно - разрешаем
    print(f"DEBUG check_contact_history: Last deal was outside threshold - OK to add")
    return {
        'can_add': True,
        'reason': 'Last interaction was outside threshold window',
        'contact': contact,
        'deals': [],
        'first_interaction': last_interaction
    }


def create_new_referal_with_validation(full_name, phone_number, user, days_threshold=45):
    """
    Создает нового реферала с проверкой истории взаимодействий.
    
    Args:
        full_name: Полное имя реферала
        phone_number: Номер телефона реферала
        user: Пользователь, создающий реферала
        days_threshold: Порог проверки в днях (по умолчанию 45)
    
    Returns:
        tuple: (referal or None, error_message or None)
    """
    # Проверяем историю контакта
    check_result = check_contact_history_before_adding(phone_number, full_name, days_threshold)
    
    if not check_result['can_add']:
        # ЗАПРЕЩЕНО добавление
        return None, check_result['reason']
    
    # Разрешено - создаем реферала
    formatted_phone = utils.format_phone_number(phone_number)
    if not formatted_phone:
        formatted_phone = phone_number
    
    contact = check_result['contact']
    contact_id = contact.contacts_id if contact else None
    
    new_referal = Referal(
        user_id=user.id,
        contact_id=contact_id,
        created_at=datetime.utcnow(),  # ВАЖНО: фиксируем дату создания
        days_window=days_threshold,
        referal_data=ReferalData(
            full_name=full_name,
            phone_number=formatted_phone,
        ),
    )
    
    print(f"DEBUG create_new_referal_with_validation: Created referal for {full_name} with window {days_threshold} days")
    
    return new_referal, None


def calculate_withdrawal_for_deal(deal):
    """
    Рассчитывает сумму выплаты для конкретного договора на основе площади.
    
    Args:
        deal: Объект MacroDeal
    
    Returns:
        int: Сумма выплаты в сумах
    """
    if not deal.deal_metr:
        return 0
    
    metr = deal.deal_metr
    
    if 20.0 <= metr < 40.0:
        return int(os.getenv('REFERAL_WITHDRAWAL_FOR_40M', 0))
    elif 40.0 <= metr < 60.0:
        return int(os.getenv('REFERAL_WITHDRAWAL_FOR_60M', 0))
    elif 60.0 <= metr < 80.0:
        return int(os.getenv('REFERAL_WITHDRAWAL_FOR_80M', 0))
    elif metr >= 80.0:
        return int(os.getenv('REFERAL_WITHDRAWAL_FOR_81M', 0))
    
    return 0


def find_and_link_deals_for_referal(referal):
    """
    Находит все договора в пределах 45-дневного окна и привязывает их к рефералу.
    
    Логика:
    1. Берем дату создания реферала (referal.created_at)
    2. Ищем все договора контакта с датой от (created_at - 45 дней) до (created_at + 45 дней)
    3. Создаем связи ReferalDeal для каждого найденного договора
    4. Считаем выплату для каждого договора отдельно
    
    Args:
        referal: Объект Referal
    
    Returns:
        list: Список созданных связей ReferalDeal
    """
    from datetime import timedelta
    
    if not referal.contact_id:
        print(f"DEBUG find_and_link_deals: Referal {referal.id} has no contact_id, skipping")
        return []
    
    # Определяем временное окно
    referal_created = referal.created_at
    window_days = referal.days_window or 45
    
    window_start = referal_created - timedelta(days=window_days)
    window_end = referal_created + timedelta(days=window_days)
    
    print(f"DEBUG find_and_link_deals: Searching deals for referal {referal.id} in window: {window_start} to {window_end}")
    
    # Находим все договора контакта
    all_deals = MacroDeal.query.filter_by(contacts_buy_id=referal.contact_id).all()
    
    print(f"DEBUG find_and_link_deals: Found {len(all_deals)} total deals for contact_id={referal.contact_id}")
    
    linked_deals = []
    
    for deal in all_deals:
        # Проверяем наличие оплат
        if not deal.has_valid_payment():
            print(f"DEBUG find_and_link_deals: Deal {deal.agreement_number} has insufficient payment, skipping")
            continue
        
        # Проверяем дату договора
        if not deal.agreement_date:
            print(f"DEBUG find_and_link_deals: Deal {deal.agreement_number} has no agreement_date, skipping")
            continue
        
        # Конвертируем date в datetime для сравнения
        deal_datetime = datetime.combine(deal.agreement_date, datetime.min.time())
        
        # Проверяем попадание в окно
        is_within_window = window_start <= deal_datetime <= window_end
        
        if not is_within_window:
            days_diff = (deal_datetime - referal_created).days
            print(f"DEBUG find_and_link_deals: Deal {deal.agreement_number} is outside window (diff: {days_diff} days), skipping")
            continue
        
        # Проверяем, не привязан ли уже этот договор к этому рефералу
        existing_link = ReferalDeal.query.filter_by(
            referal_id=referal.id,
            deal_id=deal.id
        ).first()
        
        if existing_link:
            print(f"DEBUG find_and_link_deals: Deal {deal.agreement_number} already linked to referal {referal.id}")
            linked_deals.append(existing_link)
            continue
        
        # Создаем новую связь
        days_diff = (deal_datetime - referal_created).days
        
        # Рассчитываем сумму выплаты для этого договора
        withdrawal_amount = calculate_withdrawal_for_deal(deal)
        
        referal_deal_link = ReferalDeal(
            referal_id=referal.id,
            deal_id=deal.id,
            linked_at=datetime.utcnow(),
            is_within_window=True,
            days_from_referal_creation=days_diff,
            withdrawal_amount=withdrawal_amount,
            payment_processed=False
        )
        
        db.session.add(referal_deal_link)
        linked_deals.append(referal_deal_link)
        
        print(f"✅ Linked deal {deal.agreement_number} to referal {referal.id}, withdrawal: {withdrawal_amount}, days_diff: {days_diff}")
        
        # Отправляем уведомление пользователю, если договор готов к отправке (status_id=0 и withdrawal_amount>0)
        if withdrawal_amount > 0:
            try:
                # Получаем пользователя через реферала
                user = referal.user
                if user:
                    print(f"📧 Sending deal available notification for deal {deal.agreement_number} to user {user.login}")
                    send_deal_available_notification(user, referal, deal, withdrawal_amount)
                else:
                    print(f"⚠️ No user found for referal {referal.id}, skipping notification")
            except Exception as notif_error:
                print(f"⚠️ Failed to send notification: {notif_error}")
    
    db.session.commit()
    
    print(f"DEBUG find_and_link_deals: Total linked {len(linked_deals)} deals for referal {referal.id}")
    
    return linked_deals


def update_balance_for_referal(referal, user):
    """
    Обновляет баланс пользователя на основе ВСЕХ привязанных договоров.
    Обрабатывает только те договора, для которых payment_processed=False.
    
    Args:
        referal: Объект Referal
        user: Объект User
    
    Returns:
        int: Общая сумма добавленная к балансу
    """
    # Получаем все связи referal-deal
    referal_deals = ReferalDeal.query.filter_by(
        referal_id=referal.id,
        payment_processed=False
    ).all()
    
    if not referal_deals:
        print(f"DEBUG update_balance_for_referal: No unprocessed deals for referal {referal.id}")
        return 0
    
    total_added = 0
    
    for rd in referal_deals:
        if rd.withdrawal_amount > 0:
            user.current_balance += rd.withdrawal_amount
            rd.payment_processed = True
            total_added += rd.withdrawal_amount
            
            print(f"DEBUG update_balance_for_referal: Added {rd.withdrawal_amount} to user balance for deal {rd.deal_id}")
    
    db.session.commit()
    
    print(f"✅ Total added to user {user.id} balance: {total_added} (processed {len(referal_deals)} deals)")
    
    return total_added
