"""Сервис для работы с рефералами"""

from datetime import datetime
import logging
import os
from models import *
import utils


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
            if deal_obj.deal_status_name == "Сделка проведена":
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
