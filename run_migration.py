"""
Скрипт для запуска миграции
"""
from flask import Flask
from models import db
from migrations.add_macro_contact_fields import upgrade

# Создаем приложение Flask
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'your_database_uri_here'  # Замените на вашу строку подключения
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализируем базу данных
db.init_app(app)

if __name__ == "__main__":
    with app.app_context():
        print("Running migration...")
        upgrade()
        print("Migration completed!")
