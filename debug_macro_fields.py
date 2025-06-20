"""
Скрипт для проверки доступных полей в таблице estate_deals_contacts
"""
import pymysql
from config import Config

def check_macro_fields():
    """Проверяет доступные поля в таблице estate_deals_contacts"""
    
    mysql_config = {
        'host': Config.MYSQL_HOST,
        'user': Config.MYSQL_USER,
        'password': Config.MYSQL_PASSWORD,
        'database': Config.MYSQL_DATABASE,
        'charset': 'utf8mb4'
    }
    
    try:
        connection = pymysql.connect(**mysql_config)
        cursor = connection.cursor()
        
        # Получаем структуру таблицы
        cursor.execute("DESCRIBE estate_deals_contacts")
        fields = cursor.fetchall()
        
        print("Доступные поля в таблице estate_deals_contacts:")
        for field in fields:
            print(f"- {field[0]} ({field[1]})")
        
        # Проверяем наличие email поля
        email_fields = [field[0] for field in fields if 'email' in field[0].lower()]
        print(f"\nПоля с 'email' в названии: {email_fields}")
        
        # Проверяем наличие address полей
        address_fields = [field[0] for field in fields if 'address' in field[0].lower() or 'addr' in field[0].lower()]
        print(f"Поля с 'address' в названии: {address_fields}")
        
        # Получаем пример данных
        cursor.execute("SELECT * FROM estate_deals_contacts LIMIT 1")
        sample = cursor.fetchone()
        print(f"\nПример записи: {sample}")
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        print(f"Ошибка при проверке полей: {e}")

if __name__ == "__main__":
    check_macro_fields()
