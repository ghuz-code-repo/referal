from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import os

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_data = db.relationship('UserData', backref='user', lazy=True, uselist=False)
    login = db.Column(db.String(80), unique=True, nullable=False)
    role = db.Column(db.String(50), nullable=False, default='user')
    referals = db.relationship('Referal', backref='user', lazy=True)
    current_balance = db.Column(db.Integer, default=0)
    pending_withdrawal = db.Column(db.Integer, default=0)
    total_withdrawal = db.Column(db.Integer, default=0)
    
    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f'<User {self.login}>'


class UserData(db.Model):
    #IDS
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    #Passport
    full_name = db.Column(db.String(120), nullable=False)
    passport_number = db.Column(db.String(50), nullable=True)
    passport_giver = db.Column(db.String(100), nullable=True)
    passport_date = db.Column(db.DateTime, nullable=True)
    passport_adress = db.Column(db.String(255), nullable=True)
    # mail_adress = db.Column(db.String(255), nullable=True)
    #Finance docs
    pinfl = db.Column(db.String(50), nullable=True)
    bank_name = db.Column(db.String(100), nullable=True)
    trans_schet = db.Column(db.String(50), nullable=True)
    card_number = db.Column(db.String(50), nullable=True)
    mfo = db.Column(db.String(50), nullable=True)
    #Contact data
    phone = db.Column(db.String(20), nullable=True)
    e_mail = db.Column(db.String(50), nullable=True)

class Referal(db.Model):
    #IDS
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    contact_id = db.Column(db.Integer, nullable=True)
    referal_data = db.relationship('ReferalData', backref='referal', lazy=True, uselist=False)
    deals = db.relationship('MacroDeal', backref='referal', lazy=True)
    
    #Status
    status_id = db.Column(db.Integer, db.ForeignKey('status.id'), nullable=False, default=0)
    status_name = db.Column(db.String(50), nullable=True, default='Не начата')
    rejection_reason = db.Column(db.String(1024), nullable=True)
    rejecter_name = db.Column(db.String(100), nullable=True)
    #Approvals
    initial_approval = db.Column(db.Boolean, default=False)
    analytics_approval = db.Column(db.Boolean, default=False)
    cc_approval = db.Column(db.Boolean, default=False)
    cd_approval = db.Column(db.Boolean, default=False)
    payment_amount = db.Column(db.Float, nullable=True)
    #Balance
    balance_updated = db.Column(db.Boolean, default=False)  # New field
    balance_pending_withdrawal = db.Column(db.Boolean, default=False)  # New field
    balance_withdrawn = db.Column(db.Boolean, default=False)  # New field
    withdrawal_amount = db.Column(db.Integer, default=0, nullable=True)  # New field
    
    def get_macro_contact(self):
        """Возвращает связанный MacroContact, если есть contact_id"""
        if self.contact_id:
            return MacroContact.query.filter_by(contacts_id=self.contact_id).first()
        return None

    def __repr__(self):
        return f'<Referal {self.full_name}>'

class ReferalData(db.Model):
    #IDS
    id = db.Column(db.Integer, primary_key=True)
    referal_id = db.Column(db.Integer, db.ForeignKey('referal.id'), nullable=False)
    #Agreement
    contract_date = db.Column(db.DateTime, nullable=True)
    contract_number = db.Column(db.String(50), nullable=True)
    #Personal
    full_name = db.Column(db.String(100), nullable=True, unique=True)
    passport_number = db.Column(db.String(50), nullable=True)
    passport_date = db.Column(db.DateTime, nullable=True)
    passport_giver = db.Column(db.String(100), nullable=True)
    passport_adress = db.Column(db.String(255), nullable=True)
    #Contact
    phone_number = db.Column(db.String(20), nullable=True, unique=True)
    # mail_adress = db.Column(db.String(255), nullable=True)

class MacroDeal(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    deal_status_name = db.Column(db.String(100), nullable=False)
    agreement_number = db.Column(db.String(50), nullable=False)
    contacts_buy_id = db.Column(db.Integer, nullable=False)
    deal_metr = db.Column(db.Float, nullable=True)  # New field
    referal_id = db.Column(db.Integer, db.ForeignKey('referal.id'), nullable=False, default=-1)
    
    def __repr__(self):
        return f'<MacroDeal {self.agreement_number}>'

class MacroContact(db.Model):
    __tablename__ = 'macro_contact'
    
    id = db.Column(db.Integer, primary_key=True)
    contacts_id = db.Column(db.Integer, nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    
    # Поля для паспортных данных
    passport_number = db.Column(db.String(50), nullable=True)
    passport_giver = db.Column(db.String(255), nullable=True)
    passport_date = db.Column(db.Date, nullable=True)
    passport_address = db.Column(db.Text, nullable=True)#УБРАТЬ
    email = db.Column(db.String(255), nullable=True)#УБРАТЬ
    
    # Добавляем поле номер договора
    agreement_number = db.Column(db.String(100), nullable=True)
    
    def __repr__(self):
        return f'<MacroContact {self.full_name}>'


class Manager(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    macro_id = db.Column(db.Integer, nullable=False)
    department_id = db.Column(db.Integer, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False, unique=True)
    office_name = db.Column(db.String(100), nullable=False)

class Status(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    is_final = db.Column(db.Boolean, default=False)
    is_start = db.Column(db.Boolean, default=False)


