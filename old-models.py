from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import os

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=True)  
    role = db.Column(db.String(50), nullable=False, default='user')
    full_name = db.Column(db.String(120), nullable=False)
    referrals = db.relationship('Referral', backref='user', lazy=True)
    current_balance = db.Column(db.Integer, default=0)
    pending_withdrawal = db.Column(db.Integer, default=0)
    total_withdrawal = db.Column(db.Integer, default=0)
    
    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f'<User {self.login}>'

class MacroDeal(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    deal_status_name = db.Column(db.String(100), nullable=False)
    agreement_number = db.Column(db.String(50), nullable=False)
    contacts_buy_id = db.Column(db.Integer, nullable=False)
    deal_metr = db.Column(db.Float, nullable=True)  # New field

    def __repr__(self):
        return f'<MacroDeal {self.agreement_number}>'

class MacroContact(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    contacts_id = db.Column(db.Integer, nullable=False, unique=True)
    full_name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False, unique=True)

    def __repr__(self):
        return f'<MacroContact {self.full_name}>'

class Referral(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    contact_id = db.Column(db.Integer, nullable=True)
    
    status_id = db.Column(db.Integer, db.ForeignKey('status.id'), nullable=False, default=0)
    status_name = db.Column(db.String(50), nullable=True, default='Not Started')
    rejection_reason = db.Column(db.String(255), nullable=True)
    
    initial_approval = db.Column(db.Boolean, default=False)
    analytics_approval = db.Column(db.Boolean, default=False)
    cc_approval = db.Column(db.Boolean, default=False)
    cd_approval = db.Column(db.Boolean, default=False)
    payment_amount = db.Column(db.Float, nullable=True)

    balance_updated = db.Column(db.Boolean, default=False)  # New field
    balance_pending_withdrawal = db.Column(db.Boolean, default=False)  # New field
    balance_withdrawn = db.Column(db.Boolean, default=False)  # New field
    withdrawal_amount = db.Column(db.Integer, default=0, nullable=True)  # New field

    full_name = db.Column(db.String(100), nullable=True, unique=True)
    phone_number = db.Column(db.String(20), nullable=True, unique=True)
    contract_number = db.Column(db.String(50), nullable=True)
    contract_date = db.Column(db.DateTime, nullable=True)
    def __repr__(self):
        return f'<Referral {self.full_name}>'

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
