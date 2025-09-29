"""
Migration script to add auth_user_id column to User table
"""

import sqlite3
import os
from pathlib import Path

def migrate_database():
    # Путь к базе данных
    db_path = Path(__file__).parent / "instance" / "database.db"
    
    if not db_path.exists():
        print("Database file not found, creating new database")
        return
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Проверяем, есть ли уже столбец auth_user_id
        cursor.execute("PRAGMA table_info(user)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        if 'auth_user_id' in column_names:
            print("Column auth_user_id already exists")
            conn.close()
            return
        
        # Добавляем столбец auth_user_id
        cursor.execute("ALTER TABLE user ADD COLUMN auth_user_id VARCHAR(24)")
        
        print("Successfully added auth_user_id column")
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error during migration: {e}")
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate_database()