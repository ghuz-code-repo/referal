"""
Combined script to migrate database and create test users
"""

import sqlite3
import os
from pathlib import Path
from models import User, UserData, db
from app import app

def migrate_and_create_users():
    with app.app_context():
        # Создаем таблицы если их нет
        db.create_all()
        
        # Путь к базе данных
        db_path = Path("instance/database.db")
        
        if not db_path.exists():
            print("Database file not found after db.create_all()")
            # Создаем структуру и базу данных
            db.create_all()
        
        # Добавляем столбец auth_user_id если его нет
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Проверяем, есть ли уже столбец auth_user_id
            cursor.execute("PRAGMA table_info(user)")
            columns = cursor.fetchall()
            column_names = [column[1] for column in columns]
            
            if 'auth_user_id' not in column_names:
                # Добавляем столбец auth_user_id
                cursor.execute("ALTER TABLE user ADD COLUMN auth_user_id VARCHAR(24)")
                print("Successfully added auth_user_id column")
            else:
                print("Column auth_user_id already exists")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error during migration: {e}")
            if 'conn' in locals():
                conn.close()
        
        # Проверяем, есть ли уже пользователь d.tolkunov
        existing_user = User.query.filter_by(login='d.tolkunov').first()
        if existing_user:
            print(f"User d.tolkunov already exists with ID: {existing_user.id}")
            # Обновляем auth_user_id если его нет
            if not existing_user.auth_user_id:
                existing_user.auth_user_id = '688216fa279b8a22aabeb26a'
                db.session.commit()
                print("Updated auth_user_id for existing user")
            return
        
        # Создаем нового пользователя
        user = User(
            login='d.tolkunov',
            auth_user_id='688216fa279b8a22aabeb26a',  # ID из auth-service
            role='user'
        )
        db.session.add(user)
        db.session.commit()
        
        print(f"Created user: {user.login} with auth_user_id: {user.auth_user_id}")
        
        # Создаем UserData для пользователя
        user_data = UserData(
            user_id=user.id,
            full_name='Толкунов Дмитрий Валерьевич',
            passport_number='',
            passport_giver='',
            passport_adress='',
            pinfl='',
            trans_schet='',
            card_number='',
            bank_name='',
            mfo='',
            phone='',
            e_mail=''
        )
        db.session.add(user_data)
        db.session.commit()
        
        print(f"Created UserData for user: {user.login}")

if __name__ == "__main__":
    migrate_and_create_users()