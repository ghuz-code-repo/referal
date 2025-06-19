"""Маршруты для работы с рефералами"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
import re
from models import *
from .auth_routes import get_current_user
from services import referal_service, notification_service, data_sync_service, withdrawal_service
import utils
import os

referal_bp = Blueprint('referal', __name__)


@referal_bp.route('/profile', methods=['GET'])
def profile():
    print("Profile route accessed")
    user = get_current_user()
    print(f"User after get_current_user: {user}")
    
    if not user:
        print("No user found, redirecting to main")
        return redirect(url_for('main.main'))
    
    referal_service.update_deal_info(user)
    referals = Referal.query.filter_by(user_id=user.id).all()
    print(f"Found {len(referals)} referals for user {user.login}")
    
    return render_template('profile.html', 
                          current_user=user,
                          current_balance=user.current_balance,
                          pending_withdrawal=user.pending_withdrawal,
                          total_withdrawal=user.total_withdrawal,
                          referals=referals,
                          statuses=Status.query.all())


@referal_bp.route('/add_referal', methods=['POST'])
def add_referal():
    user = get_current_user()
    print(f"User before creating referal: {user}, has ID: {user.id if user else None}")
    
    if not user:
        flash('Пожалуйста, войдите в систему', 'error')
        return redirect(url_for('main.main'))
    
    full_name = request.form.get('full_name', "").strip()
    phone_number = request.form.get('phone_number', '')

    if full_name and not re.match(r'^[A-Za-z`‘]+(?: [A-Za-z`‘]+){2,}$', full_name) or '  ' in full_name:
        flash('Не верно введено ФИО', 'error')
        return redirect(url_for('main.main'))
    
    # Updated phone validation to handle multiple phones separated by commas
    phone_numbers = [phone.strip() for phone in phone_number.split(',')]
    valid_phones = []
    
    for phone in phone_numbers:
        if re.match(r'^\+998 \d{2} \d{3} \d{2} \d{2}$', phone) and not re.search(r'(\d)\1{3,}', phone):
            valid_phones.append(phone)
        else:
            flash(f'Неверный формат телефона: {phone}. Пример верного заполнения +998 99 999 99 99', 'error')
            return redirect(url_for('main.main'))
    
    if not valid_phones:
        flash('Не указан ни один корректный номер телефона', 'error')
        return redirect(url_for('main.main'))

    # Check for existing contacts
    existing_contact = MacroContact.query.filter(
        (MacroContact.full_name == full_name) | 
        (MacroContact.phone_number.in_(valid_phones))
    ).first()
    if existing_contact:
        flash('Данный человек не может являться рефералом', 'error')
        return redirect(url_for('main.main'))

    existing_referal_data = ReferalData.query.filter(
        (ReferalData.full_name == full_name) | (ReferalData.phone_number == phone_number)
    ).first()
    if existing_referal_data:
        flash('Данный человек не может являться рефералом', 'error')
        return redirect(url_for('main.main'))
    
    else:
        try:
            new_referal = referal_service.create_new_referal(full_name, phone_number, user)
            if new_referal:
                print(f"New referal created with user_id: {new_referal.user_id}")
                db.session.add(new_referal)
                db.session.commit()
                flash('Вы успешно добавили реферала', 'success')
                utils.send_sms(phone_number, user.user_data.full_name)
                try:
                    notification_service.create_macro_task(
                        full_name=full_name,
                        phone_number=phone_number
                    )
                except Exception as e:
                    flash(f'Ошибка при создании задачи: {e}', 'error')
                utils.send_email(
                    os.getenv('MANAGER_EMAIL'),
                    'Создание встречи для реферала',
                    f'Реферер {user.user_data.full_name} добавил реферала\nПожалуйста создайте встречу для человека\n ФИО: {full_name} \n Номер телефона: {phone_number} \n')
            else:
                flash('Ошибка при создании реферала', 'error')
        except Exception as e:
            flash(f'Ошибка при добавлении реферала: {e}', 'error')

    return redirect(url_for('main.main'))


@referal_bp.route('/update_deal_info', methods=['POST'])
def update_deal_info_route():
    """Маршрут для обновления информации о сделке."""
    user = get_current_user()
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('main.main'))
        
    try:
        referal_service.update_deal_info(user)
        flash('Информация о сделке обновлена', 'success')
    except Exception as e:
        flash(f'Ошибка при обновлении информации о сделке: {e}', 'error')
    return redirect(url_for('referal.profile'))


@referal_bp.route('/request_withdrawal/<int:referal_id>', methods=['POST'])
def request_withdrawal(referal_id):
    """Маршрут для запроса на вывод средств."""
    user = get_current_user()
    try:
        withdrawal_service.request_withdrawal(referal_id, user=user)
    except Exception as e:
        flash(f'Ошибка при запросе на вывод средств: {e}', 'error')
    return redirect(url_for('referal.profile'))


@referal_bp.route('/update_referal_documents/<int:referal_id>', methods=['POST'])
def update_referal_documents(referal_id):
    """Маршрут для обновления документов реферала."""
    user = get_current_user()
    if not user:
        flash('Пожалуйста, войдите в систему', 'error')
        return redirect(url_for('main.main'))
    
    referal = Referal.query.filter_by(id=referal_id, user_id=user.id).first()
    if not referal:
        flash('Реферал не найден', 'error')
        return redirect(url_for('referal.profile'))
    
    try:
        # Если у реферала нет данных, создаем их
        if not referal.referal_data:
            referal.referal_data = ReferalData(referal_id=referal_id)
            db.session.add(referal.referal_data)
            db.session.flush()
        
        # Получаем данные из формы
        full_name = request.form.get('full_name', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        passport_number = request.form.get('passport_number', '').strip()
        passport_giver = request.form.get('passport_giver', '').strip()
        passport_adress = request.form.get('passport_adress', '').strip()
        mail_adress = request.form.get('mail_adress', '').strip()
        passport_date_str = request.form.get('passport_date', '').strip()
        
        # Обновляем поля реферала
        referal.referal_data.full_name = full_name if full_name else None
        referal.referal_data.phone_number = phone_number if phone_number else None
        referal.referal_data.passport_number = passport_number if passport_number else None
        referal.referal_data.passport_giver = passport_giver if passport_giver else None
        referal.referal_data.passport_adress = passport_adress if passport_adress else None
        referal.referal_data.mail_adress = mail_adress if mail_adress else None
        
        # Обработка passport_date с преобразованием строки в datetime
        if passport_date_str:
            try:
                passport_date = datetime.strptime(passport_date_str, '%Y-%m-%d')
                referal.referal_data.passport_date = passport_date
            except ValueError:
                try:
                    passport_date = datetime.strptime(passport_date_str, '%d.%m.%Y')
                    referal.referal_data.passport_date = passport_date
                except ValueError:
                    try:
                        passport_date = datetime.strptime(passport_date_str, '%d/%m/%Y')
                        referal.referal_data.passport_date = passport_date
                    except ValueError:
                        flash('Неверный формат даты выдачи паспорта. Используйте формат ДД.ММ.ГГГГ', 'error')
                        return redirect(url_for('referal.profile'))
        else:
            referal.referal_data.passport_date = None
        
        # Валидация ФИО
        if full_name and not re.match(r'^[A-Za-z`‘]+(?: [A-Za-z`‘]+){2,}$', full_name) or '  ' in full_name:
            flash('Неверно введено ФИО. Используйте латиницу и минимум 3 слова', 'error')
            return redirect(url_for('referal.profile'))
        
        # Валидация телефона
        if phone_number and not re.match(r'^\+998 \d{2} \d{3} \d{2} \d{2}$', phone_number):
            flash('Неверный формат телефона. Используйте формат +998 XX XXX XX XX', 'error')
            return redirect(url_for('referal.profile'))
        
        db.session.commit()
        flash('Данные реферала успешно обновлены', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при обновлении данных: {e}', 'error')
    
    return redirect(url_for('referal.profile'))


@referal_bp.route('/referal_profile/<int:referal_id>', methods=['GET'])
def referal_profile(referal_id):
    """Маршрут для отображения профиля реферала."""
    user = get_current_user()
    if not user:
        flash('Пожалуйста, войдите в систему', 'error')
        return redirect(url_for('main.main'))
    
    referal = Referal.query.filter_by(id=referal_id, user_id=user.id).first()
    if not referal:
        flash('Реферал не найден', 'error')
        return redirect(url_for('referal.profile'))
    
    return render_template('referal_profile.html', 
                          current_user=user,
                          referal=referal)


@referal_bp.route('/update_macro_data', methods=['GET'])
def update_macro_data():
    data_sync_service.fetch_data_from_mysql()
    return redirect(url_for('referal.profile'))
