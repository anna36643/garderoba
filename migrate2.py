import sqlite3

DATABASE = "garderoba.db"
conn = sqlite3.connect(DATABASE)

try:
    conn.execute("ALTER TABLE furniture RENAME COLUMN name TO name_old")
    conn.execute("ALTER TABLE furniture ADD COLUMN name TEXT")
    conn.execute("UPDATE furniture SET name = name_old")
    conn.commit()
    print("Migracja 2a: kolumna name przebudowana.")
except sqlite3.OperationalError as e:
    print("Migracja 2a pominięta:", e)

try:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS custom_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (person_id) REFERENCES persons(id)
        )
    """)
    conn.commit()
    print("Migracja 2b: tabela custom_categories utworzona.")
except sqlite3.OperationalError as e:
    print("Migracja 2b pominięta:", e)

conn.close()
