import sqlite3

DATABASE = "garderoba.db"

conn = sqlite3.connect(DATABASE)

try:
    conn.execute("ALTER TABLE users ADD COLUMN display_name TEXT")
    conn.commit()
    print("Migracja zakończona: kolumna display_name dodana.")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("Kolumna display_name już istnieje, migracja pominięta.")
    else:
        raise

conn.close()

