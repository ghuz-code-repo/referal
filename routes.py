# routes.py
# Импорты необходимых модулей и функций
from flask import render_template, request, redirect, url_for, flash, Blueprint, g, jsonify
from header_utils import decode_header_full_name

from macro_data import get_property_details
import services
from models import *
import re
from utils import month_name_genitive, send_sms
from services import update_deal_info, create_new_referral
from werkzeug.security import generate_password_hash
from models import db

from datetime import datetime
import os
from flask import send_file, request
import utils

# Создание Blueprint для маршрутов
routes_bp = Blueprint('routes', __name__)

# Функция для получения текущего пользователя из заголовков
def get_current_user():
    """Get current user information from request headers"""
    # Получение имени пользователя из заголовка аутентификации
    username = request.headers.get('X-User-Name')
    # Поиск пользователя в базе данных
    user = User.query.filter_by(login=username).first()
    
    is_admin = request.headers.get('X-User-Admin', 'false').lower() == 'true'
    full_name = decode_header_full_name(request)

    role_str = request.headers.get('X-User-Roles')
    roles = str.split(role_str, ',')
    role=''
    if 'admin' in roles or 'referal-admin' in roles:
        role = 'admin'
    elif 'referal' in roles:
        role = 'referal'
        
    if user:
        if user.role != 'admin' and is_admin:
            user.role = 'admin'
            db.session.commit()
    print(f"User found: {user}, is_admin: {is_admin}")
    # Если пользователь не найден, но у него есть доступ через шлюз (т.е. заголовок X-User-Name присутствует),
    # создаем нового пользователя в базе данных
    if not user and username:
        # Получаем дополнительную информацию из заголовков и декодируем Base64 если нужно
        full_name = decode_header_full_name(request)
        
        # Создаем нового пользователя с декодированным полным именем
        user = User(
            login=username,
            full_name=full_name,
            role = role,
            current_balance=0,
            pending_withdrawal=0,
            total_withdrawal=0,
        )
        db.session.add(user)
        
    if user and ( user.full_name!=full_name):
        user.full_name = full_name
    if user and (user.role != role):
        user.role = role
    try:
        db.session.commit()  # This should set the user.id
    except Exception as e:
        db.session.rollback()
        print(f"Error creating user: {str(e)}")
    return user

@routes_bp.route('/profile', methods=['GET'])
def profile():
    print("Profile route accessed")
    user = get_current_user()
    print(f"User after get_current_user: {user}")
    
    if not user:
        print("No user found, redirecting to main")
        # Use url_for instead of hardcoded path
        return redirect(url_for('routes.main'))
    
    update_deal_info(user)
    referrals = Referral.query.filter_by(user_id=user.id).all()
    print(f"Found {len(referrals)} referrals for user {user.login}")
    
    return render_template('profile.html', 
                          current_user=user,
                          current_balance=user.current_balance,
                          pending_withdrawal=user.pending_withdrawal,
                          total_withdrawal=user.total_withdrawal,
                          referrals=referrals,
                          statuses=Status.query.all())

@routes_bp.route('/add_referral', methods=['POST'])
def add_referral():
    user = get_current_user()
    print(f"User before creating referral: {user}, has ID: {user.id if user else None}")
    
    if not user:
        flash('Пожалуйста, войдите в систему', 'error')
        return redirect(url_for('routes.main'))
    
    """
    Маршрут для добавления реферала.

    Принимает POST-запрос с данными о реферале (ФИО и номер телефона).
    Проверяет корректность данных, наличие реферала в базе данных и добавляет нового реферала.
    Отправляет SMS-уведомление рефералу после успешного добавления.
    """
    full_name = request.form.get('full_name', "").strip()
    phone_number = request.form.get('phone_number', '')

    if not re.match(r'^[A-Za-z`]+(?: [A-Za-z`]+){2,}$', full_name) or '  ' in full_name:
        flash('Не верно введено ФИО', 'error')
        return redirect(url_for('routes.main'))
    if not re.match(r'^\+998 \d{2} \d{3} \d{2} \d{2}$', phone_number) or re.search(r'(\d)\1{3,}', phone_number):
        flash('Неверный формат телефона. Пример верного заполнения +998 99 999 99 99', 'error')
        return redirect(url_for('routes.main'))

    existing_contact = MacroContact.query.filter(
        (MacroContact.full_name == full_name) | (MacroContact.phone_number == phone_number)
    ).first()

    existing_referral = Referral.query.filter(
        (Referral.full_name == full_name) | (Referral.phone_number == phone_number)
    ).first()

    if existing_contact or existing_referral:
        flash('Данный человек не может являться рефералом', 'error')
        return redirect(url_for('routes.main'))
    else:
        try:
            new_referral = create_new_referral(full_name, phone_number, user)
            if new_referral:
                print(f"New referral created with user_id: {new_referral.user_id}")
                db.session.add(new_referral)
                db.session.commit()
                flash('Вы успешно добавили реферала', 'success')
                send_sms(phone_number, user.full_name)
                try:
                    services.create_macro_task(
                    full_name=full_name,
                    phone_number=phone_number)
                except Exception as e:
                    flash(f'Ошибка при создании задачи: {e}', 'error')
                utils.send_email(
                os.getenv('MANAGER_EMAIL'),
                'Создание встречи для реферала',
                f'Реферер {user.full_name} добавил реферала\nПожалуйста создайте встречу для человека\n ФИО: {full_name} \n Номер телефона: {phone_number} \n')
            else:
                flash('Ошибка при создании реферала', 'error')
        except Exception as e:
            flash(f'Ошибка при добавлении реферала: {e}', 'error')

    return redirect(url_for('routes.main'))

@routes_bp.route('/update_deal_info', methods=['POST'])
def update_deal_info_route():
    """
    Маршрут для обновления информации о сделке.
    Вызывает функцию update_deal_info из модуля services и обрабатывает возможные ошибки.
    """
    user = get_current_user()
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('routes.main'))
        
    try:
        update_deal_info(user)
        flash('Информация о сделке обновлена', 'success')
    except Exception as e:
        flash(f'Ошибка при обновлении информации о сделке: {e}', 'error')
    return redirect(url_for('routes.profile'))
  
@routes_bp.route('/request_withdrawal/<int:referral_id>', methods=['POST'])
def request_withdrawal(referral_id):
    """
    Маршрут для запроса на вывод средств.
    Вызывает функцию request_withwithdrawal из модуля services и обрабатывает возможные ошибки.
    """
    user = get_current_user()
    try:
        services.request_withdrawal(referral_id, user=user)
    except Exception as e:
        flash(f'Ошибка при запросе на вывод средств: {e}', 'error')
    return redirect(url_for('routes.profile'))

@routes_bp.route('/admin')
def admin_panel():
    """
    Маршрут для отображения административной панели.
    Доступен только пользователю с ролью admin.
    """
    user = get_current_user()
    # Debug the user's admin status
    if not user or not user.role == 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('routes.profile'))

    withdrawal_requests = Referral.query.filter(Referral.status_id != 0).all()
    statuses = Status.query.filter(Status.id != 0).all()
    return render_template('admin.html', 
                          current_user=user,
                          withdrawal_requests=withdrawal_requests, 
                          statuses=statuses)

@routes_bp.route('/update_withdrawal_stage/<int:referral_id>', methods=['POST'])
def update_withdrawal_stage(referral_id):
    """
    Маршрут для обновления статуса заявки на вывод средств.
    Доступен только пользователю с ролью admin.
    """
    user = get_current_user()
    # Debug the user's admin status
    if not user or not user.role == 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('routes.profile'))

    referral = Referral.query.get_or_404(referral_id)
    withdrawal_stage = int(request.form.get('withdrawal_stage'))
    rejection_reason = request.form.get('rejection_reason', '')
    #statuses = Status.query.filter(Status.is_start != True).all()
    referral.status_id = withdrawal_stage
    referral.status_name = Status.query.get(withdrawal_stage).name
    
    if withdrawal_stage == 10:
        utils.send_email(
            os.getenv('MANAGER_EMAIL'),
            'Запрос на проверку реферала',
            f'Пожалуйста созвонитесь с рефералом от {user.full_name}: ФИО: {referral.full_name} Телефон: {referral.phone_number} для проверки его данных.\n'
        )

    if withdrawal_stage == 500:
        referral.rejection_reason = rejection_reason
        user = User.query.get(referral.user_id)
        user.pending_withdrawal -= referral.withdrawal_amount
    elif withdrawal_stage == 200 and not referral.balance_withdrawn:
        user = User.query.get(referral.user_id)
        user.pending_withdrawal -= referral.withdrawal_amount
        user.total_withdrawal += referral.withdrawal_amount
        referral.balance_withdrawn = True

    db.session.commit()
    flash('Withdrawal stage updated successfully', 'success')
    return redirect(url_for('routes.admin_panel'))
  
@routes_bp.route('/get_referal_act/<int:referral_id>', methods=['POST'])
def get_referal_act(referral_id):
    """
    Маршрут для получения акта реферала.
    Генерирует DOCX-документ с информацией о реферале и отправляет его пользователю.

    """
    referral = Referral.query.filter_by(id=referral_id).first()
    if not referral:
        flash('Referral not found', 'error')
        return redirect(url_for('routes.profile'))
    
    deals = MacroDeal.query.filter_by(contacts_buy_id=referral.contact_id)
    if not deals:
        flash('Deal not found', 'error')
        return redirect(url_for('routes.profile'))

    real_deal = MacroDeal()
    for deal in deals:
        if deal.deal_status_name == "Сделка проведена" or deal.deal_status_name == "Сделка в работе":
            real_deal = deal
            break

    passport_number = request.form.get('passport_number')
    passport_giver = request.form.get('passport_giver')
    passport_date = request.form.get('passport_date')
    passport_adress = request.form.get('passport_adress')
    mail_adress=request.form.get('mail_adress')
    pinfl=request.form.get('pinfl')
    e_mail=request.form.get('e_mail')
    trans_schet = request.form.get('trans_schet')
    card_number=request.form.get('card_number')
    bank=request.form.get('bank')
    mfo=request.form.get('mfo')
    inn=request.form.get('inn')
    name=referral.full_name
    appartment_area=real_deal.deal_metr
    phone=referral.phone_number
    withdrawal_amount=referral.withdrawal_amount
    

    appartment_info = get_property_details(real_deal.agreement_number)
    # Change from dot notation to dictionary access
    project_name=appartment_info['project_name']
    house_adress=appartment_info['house_address']  # Note: fixed spelling 'address' vs 'adress'
    house_number=appartment_info['house_number']
    apartment_number=appartment_info['apartment_number']
    agreement_price=appartment_info['agreement_price']  # Note: key is 'agreement_price' not 'agreement'
    agreement_date=appartment_info['agreement_date']
    
    try:
        # Get both the document bytes and filename
        doc_bytes, output_filename = utils.get_document(
            os.getenv('ACT_DOC_NAME'),
            name=name,
            agreement_number = real_deal.agreement_number,
            passport_number=passport_number,
            passport_giver=passport_giver,
            passport_date=passport_date,
            passport_adress=passport_adress,
            agreement_day=agreement_date.day,
            agreement_month=month_name_genitive(agreement_date).lower(),
            agreement_year=agreement_date.year,
            project_name=project_name,
            house_address=house_adress,
            house_number=house_number,
            appartment_number=apartment_number,
            appartment_area=appartment_area,
            agreement_price=agreement_price,
            withdrawal_amount=withdrawal_amount,
            mail_adress=mail_adress,
            pinfl=pinfl,
            trans_schet=trans_schet,
            card_number=card_number,
            bank=bank,
            mfo=mfo,
            inn=inn,
            phone=phone,
            e_mail=e_mail)
        
        if doc_bytes and output_filename:
            # Send file directly from memory using BytesIO
            return send_file(
                doc_bytes,
                as_attachment=True,
                download_name=output_filename,
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
        else:
            flash('Failed to generate document', 'error')
    except Exception as e:
        flash(f'Ошибка при создании акта: {str(e)}', 'error')

    return redirect(url_for('routes.profile'))

@routes_bp.route('/get_referer_agreement', methods=['POST'])
def get_referer_agreement():
    """
    Маршрут для получения документа реферала.
    Генерирует DOCX-документ с информацией о реферале и отправляет его пользователю.
    """
    user = get_current_user()
    if not user:
        flash('referer not found', 'error')
        return redirect(url_for('routes.profile'))

    name = request.form.get('name')
    passport_number = request.form.get('passport_number')
    passport_giver = request.form.get('passport_giver')
    passport_date = request.form.get('passport_date')
    passport_adress = request.form.get('passport_adress')
    mail_adress=request.form.get('mail_adress')
    pinfl=request.form.get('pinfl')
    trans_schet = request.form.get('trans_schet')
    card_number=request.form.get('card_number')
    bank_name=request.form.get('bank_name')
    mfo=request.form.get('mfo')
    phone=request.form.get('phone')
    e_mail=request.form.get('e_mail')

    try:
        # Get both the document bytes and filename
        doc_bytes, output_filename = utils.get_document(
            os.getenv('AGREEMENT_DOC_NAME'),
            today_day=datetime.now().day,
            today_month=month_name_genitive(datetime.now().month).lower(), # Pass month number
            today_year=datetime.now().year,
            name=name,
            passport_number=passport_number,
            passport_giver=passport_giver,
            passport_date=passport_date,
            passport_adress=passport_adress,
            mail_adress=mail_adress,
            pinfl=pinfl,
            trans_schet=trans_schet,
            card_number=card_number,
            bank_name=bank_name,
            mfo=mfo,
            phone=phone,
            e_mail=e_mail,
            ref_name=user.full_name,
            )
        
        if doc_bytes and output_filename:
            # Send file directly from memory using BytesIO
            return send_file(
                doc_bytes,
                as_attachment=True,
                download_name=output_filename,
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
        else:
            flash('Failed to generate document', 'error')
    except Exception as e:
        flash(f'Ошибка при создании акта: {str(e)}', 'error')

    return redirect(url_for('routes.profile'))

@routes_bp.route('/force_update_contacts', methods=['GET'])
def force_update_contacts():
    """
    Маршрут для принудительного обновления контактов.
    Вызывает функцию services.fetch_data_from_mysql для обновления данных о контактах.
    """
    user = get_current_user()

    if not user or not user.role == 'admin':
        print(f"User not found or not admin: {user}")
        flash('Access denied', 'error')
        return redirect(url_for('routes.profile'))
    try:
        print("Force updating contacts...")
        services.fetch_data_from_mysql()
        flash('Контакты успешно обновлены', 'success')
    except Exception as e:
        print(f"Error during contact update: {e}")
        flash(f'Ошибка при обновлении контактов: {e}', 'error')
    
    return redirect(url_for('routes.profile'))

@routes_bp.route('/')
def home():
    """
    Маршрут для главной страницы.
    """
    return redirect(url_for('routes.main'))

@routes_bp.route('/main', methods=['GET'])
def main():
    """
    Маршрут для главной страницы после входа в систему.
    """
    user = get_current_user()
    return render_template('main.html', current_user=user)

@routes_bp.route('/debug-headers')
def debug_headers():
    """Отладочный маршрут для проверки заголовков"""
    headers = {key: value for key, value in request.headers.items()}
    decoded_name = decode_header_full_name(request)
    
    return jsonify({
        'headers': headers,
        'decoded_full_name': decoded_name,
        'encoding_header': request.headers.get('X-User-Full-Name-Encoding', 'not-set')
    })
