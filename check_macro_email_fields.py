"""
Скрипт для проверки email полей в MacroCRM
"""
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

def check_email_fields():
    mysql_config = {
        'host': os.getenv('MYSQL_HOST'),
        'user': os.getenv('MYSQL_USER'), 
        'password': os.getenv('MYSQL_PASSWORD'),
        'database': os.getenv('MYSQL_DATABASE'),
        'charset': 'utf8mb4'
    }
    
    try:
        connection = pymysql.connect(**mysql_config)
        cursor = connection.cursor()
        
        # Проверяем структуру таблицы
        cursor.execute("SHOW COLUMNS FROM estate_deals_contacts")
        columns = cursor.fetchall()
        
        print("Все поля в таблице estate_deals_contacts:")
        for col in columns:
            print(f"- {col[0]} ({col[1]})")
        
        # Ищем поля с email
        email_columns = [col[0] for col in columns if 'email' in col[0].lower()]
        print(f"\nПоля с 'email': {email_columns}")
        
        # Проверяем данные в найденных email полях
        if email_columns:
            for email_col in email_columns:
                cursor.execute(f"SELECT {email_col}, COUNT(*) FROM estate_deals_contacts WHERE {email_col} IS NOT NULL AND {email_col} != '' GROUP BY {email_col} LIMIT 10")
                data = cursor.fetchall()
                print(f"\nПримеры данных в {email_col}:")
                for row in data:
                    print(f"  {row[0]} (встречается {row[1]} раз)")
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    check_email_fields()
