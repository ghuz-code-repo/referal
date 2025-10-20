#!/usr/bin/env python3
"""Простой скрипт миграции данных из SQLite в PostgreSQL"""

import os
import psycopg2
import sqlite3
from datetime import datetime

# Настройки
SQLITE_PATH = 'instance/referal_program.db'
PG_CONN_STRING = f"host={os.getenv('POSTGRES_HOST', 'postgres')} " \
                 f"port={os.getenv('POSTGRES_PORT', '5432')} " \
                 f"dbname={os.getenv('POSTGRES_DB', 'referal_db')} " \
                 f"user={os.getenv('POSTGRES_USER', 'referal_user')} " \
                 f"password={os.getenv('POSTGRES_PASSWORD', 'ghref_2025_secure!')}"

# Конвертация boolean полей
BOOLEAN_FIELDS = {
    'status': ['is_final', 'is_start'],
    'referal': ['initial_approval', 'analytics_approval', 'cc_approval', 'cd_approval',
               'balance_updated', 'balance_pending_withdrawal', 'balance_withdrawn'],
    'referal_deal': ['is_within_window', 'payment_processed'],
    'macro_deal': ['payment_calculated']
}

# Порядок миграции таблиц
TABLE_ORDER = ['status', 'user', 'user_data', 'macro_contact', 'macro_deal', 
               'manager', 'referal', 'referal_data', 'referal_deal']


def convert_row(table_name, row, columns):
    """Конвертирует значения строки для PostgreSQL"""
    converted = list(row)
    
    # Конвертируем 0/1 в boolean для указанных полей
    if table_name in BOOLEAN_FIELDS:
        for i, col_name in enumerate(columns):
            if col_name in BOOLEAN_FIELDS[table_name] and converted[i] is not None:
                converted[i] = bool(converted[i])
    
    # Конвертируем -1 в NULL для macro_deal.referal_id
    if table_name == 'macro_deal' and 'referal_id' in columns:
        referal_id_idx = columns.index('referal_id')
        if converted[referal_id_idx] == -1:
            converted[referal_id_idx] = None
    
    return converted


def migrate():
    print("="*50)
    print("ЁЯФ„ SQLite to PostgreSQL Migration")
    print("="*50)
    
    # Подключаемся
    print("\nЁЯФМ Connecting to databases...")
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    pg_conn = psycopg2.connect(PG_CONN_STRING)
    pg_conn.autocommit = False  # Используем транзакции
    
    try:
        sqlite_cur = sqlite_conn.cursor()
        pg_cur = pg_conn.cursor()
        
        # Отключаем все triggers и constraints
        print("тЪЩя╕П  Disabling triggers...")
        pg_cur.execute("SET session_replication_role = 'replica';")
        
        # Миграция таблиц
        for table_name in TABLE_ORDER:
            print(f"\nЁЯУЛ Migrating table: {table_name}")
            
            # Читаем из SQLite
            sqlite_cur.execute(f"SELECT * FROM {table_name}")
            rows = sqlite_cur.fetchall()
            
            if not rows:
                print(f"   тЪая╕П  Table {table_name} is empty, skipping")
                continue
            
            print(f"   ЁЯУК Found {len(rows)} rows")
            
            # Получаем названия колонок
            columns = [desc[0] for desc in sqlite_cur.description]
            
            # Очищаем таблицу в PostgreSQL
            table_esc = f'"{table_name}"' if table_name == 'user' else table_name
            pg_cur.execute(f"TRUNCATE TABLE {table_esc} CASCADE")
            
            # Вставляем данные батчами
            placeholders = ','.join(['%s'] * len(columns))
            columns_str = ','.join(columns)
            insert_query = f"INSERT INTO {table_esc} ({columns_str}) VALUES ({placeholders})"
            
            batch_size = 100
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i+batch_size]
                converted_batch = [convert_row(table_name, row, columns) for row in batch]
                
                # Вставляем батч
                for row_data in converted_batch:
                    pg_cur.execute(insert_query, row_data)
                
                print(f"   ✅ Inserted {min(i+batch_size, len(rows))}/{len(rows)} rows")
            
            # Обновляем sequence
            if 'id' in columns:
                pg_cur.execute(f"SELECT setval(pg_get_serial_sequence('{table_esc}', 'id'), COALESCE(MAX(id), 1)) FROM {table_esc}")
                print(f"   тЬЕ Updated sequence for {table_name}")
        
        # Включаем triggers обратно
        print("\nтЪЩя╕П  Re-enabling triggers...")
        pg_cur.execute("SET session_replication_role = 'origin';")
        
        # Commit всех изменений
        pg_conn.commit()
        print("\nЁЯОЙ Migration completed successfully!")
        
        # Verification
        print("\n" + "="*50)
        print("ЁЯФН VERIFICATION")
        print("="*50)
        for table_name in TABLE_ORDER:
            table_esc = f'"{table_name}"' if table_name == 'user' else table_name
            sqlite_cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            sqlite_count = sqlite_cur.fetchone()[0]
            pg_cur.execute(f"SELECT COUNT(*) FROM {table_esc}")
            pg_count = pg_cur.fetchone()[0]
            
            status = "тЬЕ" if sqlite_count == pg_count else "тЭМ"
            print(f"{status} {table_name}: SQLite={sqlite_count}, PostgreSQL={pg_count}")
        
    except Exception as e:
        print(f"\nтЭМ Error: {e}")
        pg_conn.rollback()
        raise
    finally:
        sqlite_conn.close()
        pg_conn.close()


if __name__ == '__main__':
    migrate()
