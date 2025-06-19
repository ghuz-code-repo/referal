"""Маршруты для работы с документами и актами"""

from flask import Blueprint, request, redirect, url_for, flash, send_file
from datetime import datetime
import os
from .auth_routes import get_current_user
from models import *
from macro_data import get_property_details
import utils
from utils import month_name_genitive

document_bp = Blueprint('document', __name__)


@document_bp.route('/get_referal_act/<int:referal_id>', methods=['POST'])
def get_referal_act(referal_id):
    """
    Маршрут для получения акта реферала.
    Генерирует DOCX-документ с информацией о реферале и отправляет его пользователю.
    """
    referal = Referal.query.filter_by(id=referal_id).first()
    if not referal:
        flash('Referal not found', 'error')
        return redirect(url_for('referal.profile'))
    
    # Проверяем, что у реферала есть необходимые данные
    if not referal.referal_data or not referal.referal_data.passport_number:
        flash('Для генерации акта необходимо заполнить данные реферала', 'error')
        return redirect(url_for('referal.profile'))
    
    deals = MacroDeal.query.filter_by(contacts_buy_id=referal.contact_id)
    if not deals:
        flash('Deal not found', 'error')
        return redirect(url_for('referal.profile'))

    real_deal = MacroDeal()
    for deal in deals:
        if deal.deal_status_name == "Сделка проведена":
            real_deal = deal
            break

    passport_number = request.form.get('passport_number')
    passport_giver = request.form.get('passport_giver')
    passport_date = request.form.get('passport_date')
    passport_adress = request.form.get('passport_adress')
    mail_adress = request.form.get('mail_adress')
    pinfl = request.form.get('pinfl')
    e_mail = request.form.get('e_mail')
    trans_schet = request.form.get('trans_schet')
    card_number = request.form.get('card_number')
    bank = request.form.get('bank')
    mfo = request.form.get('mfo')
    inn = request.form.get('inn')
    ref_name = request.form.get('ref_name')
    name = referal.full_name
    appartment_area = real_deal.deal_metr
    phone = referal.phone_number
    withdrawal_amount = referal.withdrawal_amount
    appartment_info = get_property_details(real_deal.agreement_number)
    project_name = appartment_info['project_name']
    house_adress = appartment_info['house_address']
    house_number = appartment_info['house_number']
    apartment_number = appartment_info['apartment_number']
    agreement_price = appartment_info['agreement_price']
    agreement_date = appartment_info['agreement_date']
    
    try:
        # Get both the document bytes and filename
        doc_bytes, output_filename = utils.get_document(
            os.getenv('ACT_DOC_NAME'),
            name=name,
            agreement_number=real_deal.agreement_number,
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

    return redirect(url_for('referal.profile'))


@document_bp.route('/get_referer_agreement', methods=['POST'])
def get_referer_agreement():
    """
    Маршрут для получения документа реферала.
    Генерирует DOCX-документ с информацией о реферале и отправляет его пользователю.
    """
    user = get_current_user()
    if not user:
        flash('referer not found', 'error')
        return redirect(url_for('referal.profile'))

    userinfo = UserData.query.filter_by(user_id=user.id).first()
    if not userinfo:
        flash('Заполните данные реферера', 'error')
        return redirect(url_for('referal.profile'))

    try:
        doc_bytes, output_filename = utils.get_document(
            os.getenv('AGREEMENT_DOC_NAME'),
            today_day=datetime.now().day,
            today_month=month_name_genitive(datetime.now().month).lower(),
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

    return redirect(url_for('referal.profile'))
