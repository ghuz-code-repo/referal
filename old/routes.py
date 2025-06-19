# routes.py
# Импорты необходимых модулей и функций
from flask import render_template, request, redirect, url_for, flash, Blueprint, g, jsonify
from header_utils import decode_header_full_name

from macro_data import get_property_details
import services
from models import *
import re
from utils import month_name_genitive, send_sms
from services import update_deal_info, create_new_referal
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

    if 'referal' in roles:
        role = 'referal'
    if 'referal-manager' in roles:
        role = 'manager' 
    if 'admin' in roles or 'referal-admin' in roles:
        role = 'admin'  
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
            role = role,
            current_balance=0,
            pending_withdrawal=0,
            total_withdrawal=0
        )
        
        db.session.add(user)
        try:
            db.session.commit()  # This should set the user.id
        except Exception as e:
            db.session.rollback()
            print(f"Error creating user first time: {str(e)}")
        
        user_data=UserData(
            user_id=user.id,
            full_name=full_name
        )

        user.user_data = user_data
        db.session.add(user)
    if user and not user.user_data:
        # Если у пользователя нет связанных данных, создаем их
        user.user_data = UserData(user_id=user.id, full_name=full_name)

    if user and (user.user_data.full_name != full_name):
        user.user_data.full_name = full_name
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
    referals = Referal.query.filter_by(user_id=user.id).all()
    print(f"Found {len(referals)} referals for user {user.login}")
    
    return render_template('profile.html', 
                          current_user=user,
                          current_balance=user.current_balance,
                          pending_withdrawal=user.pending_withdrawal,
                          total_withdrawal=user.total_withdrawal,
                          referals=referals,
                          statuses=Status.query.all())

@routes_bp.route('/add_referal', methods=['POST'])
def add_referal():
    user = get_current_user()
    print(f"User before creating referal: {user}, has ID: {user.id if user else None}")
    
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

    if not re.match(r'^[A-Za-z`‘]+(?: [A-Za-z`‘]+){2,}$', full_name) or '  ' in full_name:
        flash('Не верно введено ФИО', 'error')
        return redirect(url_for('routes.main'))
    
    # Updated phone validation to handle multiple phones separated by commas
    # Split by comma and validate each phone separately
    phone_numbers = [phone.strip() for phone in phone_number.split(',')]
    valid_phones = []
    
    for phone in phone_numbers:
        # Validate each phone number individually
        if re.match(r'^\+998 \d{2} \d{3} \d{2} \d{2}$', phone) and not re.search(r'(\d)\1{3,}', phone):
            valid_phones.append(phone)
        else:
            flash(f'Неверный формат телефона: {phone}. Пример верного заполнения +998 99 999 99 99', 'error')
            return redirect(url_for('routes.main'))
    
    if not valid_phones:
        flash('Не указан ни один корректный номер телефона', 'error')
        return redirect(url_for('routes.main'))

    # Check for existing contacts with any of the provided phone numbers
    existing_contact = MacroContact.query.filter(
        (MacroContact.full_name == full_name) | 
        (MacroContact.phone_number.in_(valid_phones))
    ).first()
    if existing_contact :
        flash('Данный человек не может являться рефералом', 'error')
        return redirect(url_for('routes.main'))

    existing_referal_data = ReferalData.query.filter(
        (ReferalData.full_name == full_name) | (ReferalData.phone_number == phone_number)
    ).first()
    if existing_referal_data:
        flash('Данный человек не может являться рефералом', 'error')
        return redirect(url_for('routes.main'))
    
    # existing_referal = Referal.query.filter(
    #     (existing_referal_data.referal_id == Referal.id)
    # ).first()
    # if  existing_referal:
    #     flash('Данный человек не может являться рефералом', 'error')
    #     return redirect(url_for('routes.main'))

    else:
        try:
            new_referal = create_new_referal(full_name, phone_number, user)
            if new_referal:
                print(f"New referal created with user_id: {new_referal.user_id}")
                db.session.add(new_referal)
                db.session.commit()
                flash('Вы успешно добавили реферала', 'success')
                send_sms(phone_number, user.user_data.full_name)
                try:
                    services.create_macro_task(
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
  
@routes_bp.route('/request_withdrawal/<int:referal_id>', methods=['POST'])
def request_withdrawal(referal_id):
    """
    Маршрут для запроса на вывод средств.
    Вызывает функцию request_withwithdrawal из модуля services и обрабатывает возможные ошибки.
    """
    user = get_current_user()
    try:
        services.request_withdrawal(referal_id, user=user)
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

    withdrawal_requests = Referal.query.filter(Referal.status_id != 0).all()
    statuses = Status.query.filter(Status.id != 0).all()
    return render_template('admin.html', 
                          current_user=user,
                          withdrawal_requests=withdrawal_requests, 
                          statuses=statuses)

@routes_bp.route('/update_withdrawal_stage/<int:referal_id>', methods=['POST'])
def update_withdrawal_stage(referal_id):
    """
    Маршрут для обновления статуса заявки на вывод средств.
    Доступен только пользователю с ролью admin.
    """
    user = get_current_user()
    # Debug the user's admin status
    if not user or not user.role == 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('routes.profile'))

    referal = Referal.query.get_or_404(referal_id)
    withdrawal_stage = int(request.form.get('withdrawal_stage'))
    rejection_reason = request.form.get('rejection_reason', '')
    #statuses = Status.query.filter(Status.is_start != True).all()
    referal.status_id = withdrawal_stage
    referal.status_name = Status.query.get(withdrawal_stage).name
    
    if withdrawal_stage == 10:
        utils.send_email(
            os.getenv('MANAGER_EMAIL'),
            'Запрос на проверку реферала',
            f'Пожалуйста созвонитесь с рефералом от {user.user_data.full_name}: ФИО: {referal.referal_data.full_name} Телефон: {referal.referal_data.phone_number} для проверки его данных.\n'
        )

    if withdrawal_stage == 500:
        referal.rejection_reason = rejection_reason
        user = User.query.get(referal.user_id)
        user.pending_withdrawal -= referal.withdrawal_amount
    elif withdrawal_stage == 200 and not referal.balance_withdrawn:
        user = User.query.get(referal.user_id)
        user.pending_withdrawal -= referal.withdrawal_amount
        user.total_withdrawal += referal.withdrawal_amount
        referal.balance_withdrawn = True

    db.session.commit()
    flash('Withdrawal stage updated successfully', 'success')
    return redirect(url_for('routes.admin_panel'))
  
@routes_bp.route('/get_referal_act/<int:referal_id>', methods=['POST'])
def get_referal_act(referal_id):
    """
    Маршрут для получения акта реферала.
    Генерирует DOCX-документ с информацией о реферале и отправляет его пользователю.
    """
    referal = Referal.query.filter_by(id=referal_id).first()
    if not referal:
        flash('Referal not found', 'error')
        return redirect(url_for('routes.profile'))
    
    # Проверяем, что у реферала есть необходимые данные
    if not referal.referal_data or not referal.referal_data.passport_number:
        flash('Для генерации акта необходимо заполнить данные реферала', 'error')
        return redirect(url_for('routes.profile'))
    
    deals = MacroDeal.query.filter_by(contacts_buy_id=referal.contact_id)
    if not deals:
        flash('Deal not found', 'error')
        return redirect(url_for('routes.profile'))

    real_deal = MacroDeal()
    for deal in deals:
        if deal.deal_status_name == "Сделка проведена":
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
    ref_name = request.form.get('ref_name')
    name=referal.full_name
    appartment_area=real_deal.deal_metr
    phone=referal.phone_number
    withdrawal_amount=referal.withdrawal_amount
    appartment_info = get_property_details(real_deal.agreement_number)
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
            e_mail=e_mail,
            ref_name=ref_name)

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

    userinfo= UserData.query.filter_by(user_id=user.id).first()
    if not userinfo:
        flash('Заполните данные реферера', 'error')
        return redirect(url_for('routes.profile'))

    try:
        # Get both the document bytes and filename
        doc_bytes, output_filename = utils.get_document(
            os.getenv('AGREEMENT_DOC_NAME'),
            today_day=datetime.now().day,
            today_month=month_name_genitive(datetime.now().month).lower(), # Pass month number
            today_year=datetime.now().year,
            name=userinfo.name,
            passport_number=userinfo.passport_number,
            passport_giver=userinfo.passport_giver,
            passport_date=userinfo.passport_date,
            passport_adress=userinfo.passport_adress,
            mail_adress=userinfo.mail_adress,
            pinfl=userinfo.pinfl,
            trans_schet=userinfo.trans_schet,
            card_number=userinfo.card_number,
            bank_name=userinfo.bank_name,
            mfo=userinfo.mfo,
            phone=userinfo.phone,
            e_mail=userinfo.e_mail,
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

@routes_bp.route('/update_user_info', methods=['POST'])  
def update_user_info():
    """
    Функция для обновления информации о пользователе.
    Проверяет наличие пользователя и обновляет его данные.
    """
    user = get_current_user()
    if not user:
        flash('Пожалуйста, войдите в систему', 'error')
        return redirect(url_for('routes.main'))
    
    userinfo = UserData.query.filter_by(user_id=user.id).first()
    if not userinfo:
        userinfo = UserData(
            user_id=user.id,
            name = request.form.get('name'),
            passport_number = request.form.get('passport_number'),
            passport_giver = request.form.get('passport_giver'),
            passport_date = request.form.get('passport_date'),
            passport_adress = request.form.get('passport_adress'),
            mail_adress=request.form.get('mail_adress'),
            pinfl=request.form.get('pinfl'),
            trans_schet = request.form.get('trans_schet'),
            card_number=request.form.get('card_number'),
            bank_name=request.form.get('bank_name'),
            mfo=request.form.get('mfo'),
            phone=request.form.get('phone'),
            e_mail=request.form.get('e_mail')
        )

@routes_bp.route('/update_referal_info/<int:referal_id>', methods=['POST'])
def update_referal_info(referal_id):
    """
    Функция для обновления информации о реферале.
    Проверяет наличие реферала и обновляет его данные.
    """
    
    user = get_current_user()
    if not user:
        flash('Пожалуйста, войдите в систему', 'error')
        return redirect(url_for('routes.main'))
    
    user_info = UserData.query.filter_by(user_id=user.id).first()
    if not user_info:
        flash('Пожалуйста, заполните данные реферера', 'error')
        return redirect(url_for('routes.profile'))
    
    referal = Referal.query.filter_by(id=referal_id).first()
    if not referal:
        flash('Referal not found', 'error')
        return redirect(url_for('routes.profile'))
    
    deals = MacroDeal.query.filter_by(contacts_buy_id=referal.contact_id)
    if not deals:
        flash('Deal not found', 'error')
        return redirect(url_for('routes.profile'))

    real_deal = MacroDeal()
    for deal in deals:
        if deal.deal_status_name == "Сделка проведена": #or deal.deal_status_name == "Сделка в работе":
            real_deal = deal
            break
        
    appartment_info = get_property_details(real_deal.agreement_number)
    
    referal_data = ReferalData.query.filter_by(referal_id=referal_id).first()
    if not referal_data:
        referal_data = ReferalData(
            referal_id=referal_id,
            passport_number = request.form.get('passport_number'),
            passport_giver = request.form.get('passport_giver'),
            passport_date = request.form.get('passport_date'),
            passport_adress = request.form.get('passport_adress'),
            mail_adress = request.form.get('mail_adress'),
            pinfl = request.form.get('pinfl'),
            e_mail = request.form.get('e_mail'),
            trans_schet = request.form.get('trans_schet'),
            card_number = request.form.get('card_number'),
            bank = request.form.get('bank'),
            mfo = request.form.get('mfo'),
            inn = request.form.get('inn'),
            ref_name = request.form.get('ref_name'),
            name = referal.full_name,
            appartment_area = real_deal.deal_metr,
            phone = referal.phone_number,
            withdrawal_amount = referal.withdrawal_amount,
            appartment_info = get_property_details(real_deal.agreement_number),
            project_name = appartment_info['project_name'],
            house_adress = appartment_info['house_address'],
            house_number = appartment_info['house_number'],
            apartment_number = appartment_info['apartment_number'],
            agreement_price = appartment_info['agreement_price'],
            agreement_date = appartment_info['agreement_date']
        )

@routes_bp.route('/update_macro_data', methods=['GET'])
def update_macro_data():
    services.fetch_data_from_mysql()
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

@routes_bp.route('/referal_profile/<int:referal_id>', methods=['GET'])
def referal_profile(referal_id):
    """
    Маршрут для отображения профиля реферала.
    Позволяет просматривать и редактировать данные реферала.
    """
    user = get_current_user()
    if not user:
        flash('Пожалуйста, войдите в систему', 'error')
        return redirect(url_for('routes.main'))
    
    # Проверяем, что реферал принадлежит текущему пользователю
    referal = Referal.query.filter_by(id=referal_id, user_id=user.id).first()
    if not referal:
        flash('Реферал не найден', 'error')
        return redirect(url_for('routes.profile'))
    
    return render_template('referal_profile.html', 
                          current_user=user,
                          referal=referal)

@routes_bp.route('/update_referal_documents/<int:referal_id>', methods=['POST'])
def update_referal_documents(referal_id):
    """
    Маршрут для обновления документов реферала.
    Обновляет только поля реферала в ReferalData.
    """
    user = get_current_user()
    if not user:
        flash('Пожалуйста, войдите в систему', 'error')
        return redirect(url_for('routes.main'))
    
    # Проверяем, что реферал принадлежит текущему пользователю
    referal = Referal.query.filter_by(id=referal_id, user_id=user.id).first()
    if not referal:
        flash('Реферал не найден', 'error')
        return redirect(url_for('routes.profile'))
    
    # Детальная отладка - выводим все данные формы
    print(f"=== DEBUGGING update_referal_documents for referal_id={referal_id} ===")
    print(f"Form data received:")
    for key, value in request.form.items():
        print(f"  {key}: '{value}'")
    
    # Проверяем существующие данные реферала
    print(f"Current referal.referal_data: {referal.referal_data}")
    if referal.referal_data:
        print(f"  Current full_name: '{referal.referal_data.full_name}'")
        print(f"  Current phone_number: '{referal.referal_data.phone_number}'")
        print(f"  Current passport_date: '{referal.referal_data.passport_date}'")
    
    try:
        # Если у реферала нет данных, создаем их
        if not referal.referal_data:
            print("Creating new ReferalData...")
            referal.referal_data = ReferalData(referal_id=referal_id)
            db.session.add(referal.referal_data)
            # Коммитим сначала создание, чтобы получить ID
            db.session.flush()
            print(f"Created ReferalData with ID: {referal.referal_data.id}")
        
        # Получаем данные из формы (ИСПРАВЛЕНО: правильное имя поля date вместо passport_date)
        full_name = request.form.get('full_name', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        passport_number = request.form.get('passport_number', '').strip()
        passport_giver = request.form.get('passport_giver', '').strip()
        passport_adress = request.form.get('passport_adress', '').strip()
        mail_adress = request.form.get('mail_adress', '').strip()
        passport_date_str = request.form.get('passport_date', '').strip()
        
        print(f"Extracted form data:")
        print(f"  full_name: '{full_name}'")
        print(f"  phone_number: '{phone_number}'")
        print(f"  passport_date_str: '{passport_date_str}'")
        
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
                # Пытаемся парсить дату в формате YYYY-MM-DD (HTML date input)
                passport_date = datetime.strptime(passport_date_str, '%Y-%m-%d')
                referal.referal_data.passport_date = passport_date
                print(f"Successfully parsed passport_date: {passport_date_str} -> {passport_date}")
            except ValueError:
                try:
                    # Пытаемся парсить дату в формате DD.MM.YYYY (пользовательский ввод)
                    passport_date = datetime.strptime(passport_date_str, '%d.%m.%Y')
                    referal.referal_data.passport_date = passport_date
                    print(f"Successfully parsed passport_date (DD.MM.YYYY): {passport_date_str} -> {passport_date}")
                except ValueError:
                    try:
                        # Пытаемся парсить дату в формате DD/MM/YYYY
                        passport_date = datetime.strptime(passport_date_str, '%d/%m/%Y')
                        referal.referal_data.passport_date = passport_date
                        print(f"Successfully parsed passport_date (DD/MM/YYYY): {passport_date_str} -> {passport_date}")
                    except ValueError:
                        print(f"Failed to parse passport_date: {passport_date_str}")
                        flash('Неверный формат даты выдачи паспорта. Используйте формат ДД.ММ.ГГГГ', 'error')
                        return redirect(url_for('routes.profile'))
        else:
            # Если поле пустое, устанавливаем None
            referal.referal_data.passport_date = None
            print("Set passport_date to None (empty field)")
        
        # Валидация ФИО
        if full_name and not re.match(r'^[A-Za-z`‘]+(?: [A-Za-z`‘]+){2,}$', full_name) or '  ' in full_name:
            flash('Неверно введено ФИО. Используйте латиницу и минимум 3 слова', 'error')
            return redirect(url_for('routes.profile'))
        
        # Валидация телефона
        if phone_number and not re.match(r'^\+998 \d{2} \d{3} \d{2} \d{2}$', phone_number):
            flash('Неверный формат телефона. Используйте формат +998 XX XXX XX XX', 'error')
            return redirect(url_for('routes.profile'))
        
        print(f"Before commit - referal_data fields:")
        print(f"  full_name: '{referal.referal_data.full_name}'")
        print(f"  phone_number: '{referal.referal_data.phone_number}'")
        print(f"  passport_date: '{referal.referal_data.passport_date}'")
        
        # Коммитим изменения
        db.session.commit()
        
        print(f"After commit - referal_data fields:")
        print(f"  full_name: '{referal.referal_data.full_name}'")
        print(f"  phone_number: '{referal.referal_data.phone_number}'")
        print(f"  passport_date: '{referal.referal_data.passport_date}'")
        
        flash('Данные реферала успешно обновлены', 'success')
        print(f"Successfully updated referal documents for ID {referal_id}")
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating referal documents: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        flash(f'Ошибка при обновлении данных: {e}', 'error')
    
    print(f"=== END DEBUGGING ===")
    return redirect(url_for('routes.profile'))
